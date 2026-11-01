import { DOMParser } from 'xmldom'
import NodeInstaRequests from './NodeInstaRequests.js'
import HttpsProxyAgent from 'https-proxy-agent'
import { SocksProxyAgent } from 'socks-proxy-agent'
import LiveVideoRecorder from './LiveVideoRecorder.js'
import { createWriteStream, createReadStream } from 'fs'
import { rm } from 'fs/promises'
import { resolve } from 'path'
import { finished } from 'node:stream/promises'
import { writeFile, readFile } from 'node:fs/promises'
import ffmpeg from 'fluent-ffmpeg'
import ansiEscapes from 'ansi-escapes'

const dirname = 'E:\\WORK\\INSTAGRAM'
const rectime = new Date().toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' }).replace(/[/:\s]/g, '-').replace(/,/g, '');
const rnd = Math.floor(Math.random() * 100000)

async function makeRecords (liveRecorder, tryToFetchBegining, leaveTemp, verbose) {
  const startTime = liveRecorder.startTime
  const videoTempPath = resolve(dirname, 'Temp', `${startTime}-video-temp-${startTime}_${rnd}.m4v`)
  const audioTempPath = resolve(dirname, 'Temp', `${startTime}-audio-temp-${startTime}_${rnd}.m4a`)
  const tempVideoOutput = createWriteStream(videoTempPath)
  const tempAudioOutput = createWriteStream(audioTempPath)
  const initialVideoBuffer = Buffer.from(await liveRecorder.videoInitBlob.arrayBuffer())
  const initialAudioBuffer = Buffer.from(await liveRecorder.audioInitBlob.arrayBuffer())
  if (!tryToFetchBegining) {
    tempVideoOutput.write(initialVideoBuffer)
    tempAudioOutput.write(initialAudioBuffer)
  }
  const { videoStream, audioStream } = liveRecorder.getDataStreams()
 
  videoStream.pipe(tempVideoOutput)
  audioStream.pipe(tempAudioOutput)
 
  await liveRecorder.startRecording()
  await finished(videoStream)
  await finished(audioStream)
  // Wait for the destination files too; a readable stream finishing does
  // not by itself guarantee that the piped file handles have flushed.
  await finished(tempVideoOutput)
  await finished(tempAudioOutput)

  if (tryToFetchBegining && liveRecorder.userCancelled) {
    // On user cancellation, do not spend extra time fetching the earlier
    // broadcast. Build a valid partial elementary stream from the init blob
    // plus all segments already downloaded.
    const videoPath = resolve(dirname, 'Temp', `${startTime}-video-partial-${startTime}_${rnd}.m4v`)
    const audioPath = resolve(dirname, 'Temp', `${startTime}-audio-partial-${startTime}_${rnd}.m4a`)
    const videoOutput = createWriteStream(videoPath)
    const audioOutput = createWriteStream(audioPath)
    videoOutput.write(initialVideoBuffer)
    audioOutput.write(initialAudioBuffer)
    const videoInput = createReadStream(videoTempPath)
    const audioInput = createReadStream(audioTempPath)
    videoInput.pipe(videoOutput)
    audioInput.pipe(audioOutput)
    await finished(videoInput)
    await finished(audioInput)
    await finished(videoOutput)
    await finished(audioOutput)
    if (!leaveTemp) {
      await rm(videoTempPath, { force: true })
      await rm(audioTempPath, { force: true })
    }
    return { startTime, videoPath, audioPath, partial: true }
  }

  if (tryToFetchBegining) {
    const videoPath = resolve(dirname, 'Temp', `${startTime}-video-${startTime}_${rnd}.m4v`)
    const audioPath = resolve(dirname, 'Temp', `${startTime}-audio-${startTime}_${rnd}.m4a`)

    const videoOutput = createWriteStream(videoPath)
    const audioOutput = createWriteStream(audioPath)

    const { pastVideoStream, pastAudioStream } = liveRecorder.getPastDataStreams()
    videoOutput.write(initialVideoBuffer)
    audioOutput.write(initialAudioBuffer)    
    pastVideoStream.pipe(videoOutput, { end: false })
    pastAudioStream.pipe(audioOutput, { end: false })

    await liveRecorder.tryFetchBack(verbose)
    await finished(pastVideoStream)
    await finished(pastAudioStream)
    createReadStream(videoTempPath).pipe(videoOutput)
    createReadStream(audioTempPath).pipe(audioOutput)
    await finished(videoOutput)
    await finished(audioOutput)
    if (!leaveTemp) {
      rm(videoTempPath)
      rm(audioTempPath)
    }
    
    return {
      startTime,
      videoPath,
      audioPath, 
    }
  }

  return {
    startTime,
    videoPath: videoTempPath,
    audioPath: audioTempPath,
    partial: Boolean(liveRecorder.userCancelled),
  }
}


async function collectLiveComments(insta, broadcastId, startedAt, outputFile, intervalMs = 5000, verbose = false, username = '') {
  const comments = []
  let lastCommentTs = 0
  let stopped = false
  let blocked = false
  let inFlight = Promise.resolve()
  let timer
  let consecutiveFailures = 0

  const poll = async () => {
    if (stopped || blocked) return
    const response = await insta.getLiveComments(broadcastId, lastCommentTs, username)
    if (!response.ok) {
      const message = String(response.error || 'unknown error')
      if (response.blocked || /challenge_required|checkpoint_required|login_required|non-json comments response|html page/i.test(message)) {
        blocked = true
        console.warn('[Comments] Instagram did not return comment JSON. Comment polling is paused; video recording continues. Check the Instagram login/session in the official app or website before the next recording.')
      } else {
        consecutiveFailures += 1
        const waitSeconds = Math.min(60, Math.max(5, Number(intervalMs) / 1000) * (2 ** Math.min(consecutiveFailures - 1, 4)))
        if (verbose) console.warn(`[Comments] Temporary request failure (${consecutiveFailures}); retry interval increased to ${waitSeconds}s: ${message}`)
        nextDelayMs = waitSeconds * 1000
      }
      return
    }

    consecutiveFailures = 0
    nextDelayMs = Math.max(2000, Number(intervalMs) || 5000)
    const batch = Array.isArray(response.json?.comments) ? response.json.comments : []
    for (const item of batch) {
      if (!item || typeof item !== 'object') continue
      const created = Number(item.created_at_utc || item.timestamp || 0)
      if (created) lastCommentTs = Math.max(lastCommentTs, created)
      const createdSeconds = created > 1e12 ? created / 1000 : created
      const elapsed = createdSeconds > 0
        ? Math.max(0, createdSeconds - (startedAt / 1000))
        : Math.max(0, (Date.now() - startedAt) / 1000)
      comments.push({ ...item, total_elapsed: Math.round(elapsed * 1000) / 1000 })
    }
    if (batch.length && verbose) console.log(`[Comments] ${batch.length} new comment(s), total ${comments.length}`)
  }

  let nextDelayMs = Math.max(2000, Number(intervalMs) || 5000)
  await poll()
  const scheduleNext = () => {
    if (stopped || blocked) return
    timer = setTimeout(() => {
      // Never overlap comment requests. Slow responses must not create a queue
      // of simultaneous requests while the video segment downloader runs.
      inFlight = poll()
        .catch(error => verbose && console.warn(`[Comments] ${error.message}`))
        .finally(scheduleNext)
    }, nextDelayMs)
  }
  scheduleNext()

  return {
    async stop() {
      stopped = true
      clearTimeout(timer)
      await inFlight
      if (!comments.length) {
        if (verbose) console.log('[Comments] No comments were collected.')
        return null
      }

      const jsonPath = outputFile.replace(/\.mp4$/i, '.json')
      const srtPath = outputFile.replace(/\.mp4$/i, '.chat.srt')
      await writeFile(jsonPath, JSON.stringify({ comments }, null, 2), 'utf8')

      const formatSrtTime = (seconds) => {
        const totalMs = Math.max(0, Math.round(Number(seconds || 0) * 1000))
        const hours = Math.floor(totalMs / 3600000)
        const minutes = Math.floor((totalMs % 3600000) / 60000)
        const secs = Math.floor((totalMs % 60000) / 1000)
        const millis = totalMs % 1000
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(millis).padStart(3, '0')}`
      }

      const cues = comments.map((c) => {
        let elapsed = Number(c.total_elapsed)
        if (!Number.isFinite(elapsed)) {
          const timestamp = Number(c.created_at_utc || c.timestamp || 0)
          elapsed = timestamp > 0 ? timestamp - (startedAt / 1000) : 0
        }
        elapsed = Math.max(0, elapsed)
        const author = String(c.user?.username || c.username || c.user?.full_name || 'unknown').trim()
        const body = String(c.text || c.message || '').replace(/[\r\n]+/g, ' ').trim()
        return { elapsed, text: `${author}: ${body}` }
      }).filter(c => c.text.length > 0).sort((a, b) => a.elapsed - b.elapsed)

      const srtLines = []
      cues.forEach((cue, index) => {
        srtLines.push(String(index + 1), `${formatSrtTime(cue.elapsed)} --> ${formatSrtTime(cue.elapsed + 5)}`, cue.text, '')
      })
      await writeFile(srtPath, srtLines.join('\n'), 'utf8')
      console.log(`[Comments] Saved ${comments.length} comment(s): ${jsonPath}`)
      console.log(`[Comments] SRT subtitle: ${srtPath}`)
      return { jsonPath, srtPath, count: comments.length }
    }
  }
}

// Read a Netscape/Mozilla cookies.txt file and build the Cookie header
// applicable to https://www.instagram.com/. This mirrors PyInstaLive's
// MozillaCookieJar behavior (including cookies whose expiry has passed).
async function loadInstagramCookieFile(cookiesFile) {
  if (!cookiesFile) return { cookieString: '', csrfToken: '' }

  const raw = await readFile(cookiesFile, 'utf8')
  const targetHost = 'www.instagram.com'
  const targetPath = '/api/v1/live/'
  const now = Math.floor(Date.now() / 1000)
  const selected = new Map()

  for (const originalLine of raw.split(/\r?\n/)) {
    let line = originalLine.trim()
    if (!line) continue

    // Netscape cookie files encode HttpOnly rows as #HttpOnly_<domain>.
    if (line.startsWith('#HttpOnly_')) {
      line = line.slice('#HttpOnly_'.length)
    } else if (line.startsWith('#')) {
      continue
    }

    const fields = line.split('\t')
    if (fields.length < 7) continue

    const [rawDomain, includeSubdomains, cookiePath, secure, expiresText, name, value] = fields
    const domain = rawDomain.replace(/^\./, '').toLowerCase()
    const cookieName = String(name || '').trim()
    if (!domain || !cookieName) continue

    const domainMatches =
      targetHost === domain ||
      (String(includeSubdomains).toUpperCase() === 'TRUE' && targetHost.endsWith(`.${domain}`))
    if (!domainMatches) continue

    const path = cookiePath || '/'
    if (!targetPath.startsWith(path.endsWith('/') ? path : `${path}/`) &&
        targetPath !== path) continue
    if (String(secure).toUpperCase() === 'TRUE' && !targetHost) continue

    // Keep expiry semantics aligned with PyInstaLive's
    // MozillaCookieJar.load(ignore_discard=True, ignore_expires=True).
    selected.set(cookieName, String(value))
  }

  const cookieString = [...selected.entries()]
    .map(([name, value]) => `${name}=${value}`)
    .join('; ')
  const csrfToken = selected.get('csrftoken') || ''
  const sessionId = selected.get('sessionid') || ''
  return { cookieString, csrfToken, sessionId }
}

export async function recordLiveStream ({ 
  username, 
  userId, 
  mpdUrl, 
  csrfToken, 
  sessionId, 
  cookiesFile,
  proxy, 
  getFull: tryToFetchBegining,
  ffmpegOutputOptions,
  outputFile,
  leaveTemp,
  verbose,
  downloadComments = true,
  commentInterval = 5000,
 }) {
  const eventLoopFix = () => setTimeout(eventLoopFix, 99999999)
  const fixTimeout = setTimeout(eventLoopFix, 99999999)
 
  let agent
  if (proxy) {
    if (proxy.startsWith('http')) {
      agent = new HttpsProxyAgent(proxy)
    } else if (proxy.startsWith('socks')) {
      agent = new SocksProxyAgent(proxy)
    }
  }
  
  if (!cookiesFile || !String(cookiesFile).trim()) {
    throw new Error('[Auth] cookiesFile is required. Set the path to your Instagram cookies.txt file in config.json.')
  }

  let cookieData
  try {
    cookieData = await loadInstagramCookieFile(cookiesFile)
  } catch (error) {
    throw new Error(`[Auth] Could not read required cookiesFile: ${error.message}`)
  }

  const cookieString = cookieData.cookieString
  const effectiveCsrfToken = cookieData.csrfToken
  const effectiveSessionId = cookieData.sessionId
  const cookieCount = cookieString ? cookieString.split('; ').length : 0
  if (!cookieString || !effectiveCsrfToken || !effectiveSessionId) {
    throw new Error('[Auth] cookiesFile must contain applicable Instagram cookies including both csrftoken and sessionid. No recording was started.')
  }
  if (verbose) {
    console.log(`[Auth] Loaded ${cookieCount} applicable Instagram cookies from cookiesFile (csrftoken and sessionid found).`)
  }

  const insta = new NodeInstaRequests({
    csrfToken: effectiveCsrfToken,
    sessionId: effectiveSessionId,
    cookieString,
    agent,
    xmlParser: new DOMParser(),
  })
  const liveRecorder = new LiveVideoRecorder(insta)
  const saveAndExitSignal = () => liveRecorder.stopRecording()
  if (verbose) {
    liveRecorder.addEventListener('segment-downloaded', (e) => {
      console.log(`Segment ${e.details.segmentNumber} downloaded`)
    })
  }
  let initStatus
 
  let outputRecordFile
  if (mpdUrl) {
    initStatus = await liveRecorder.initializeWithMpdUrl(mpdUrl)
    outputRecordFile = `Instalive@${username  || userId || 'record_'}${rectime}.mp4`    
  } else if (userId) {
    initStatus = await liveRecorder.initializeWithUserId(userId) 
    outputRecordFile = `Instalive@${username || userId}_${rectime}.mp4`    
  } else if (username) {
    initStatus = await liveRecorder.initializeWithUsername(username)
    outputRecordFile = `Instalive@${username}_${rectime}.mp4`
  } else {
    throw new Error('You need to provide mpdUrl, userId or username')
  }
  const outputRecordPath = outputFile || resolve(dirname, outputRecordFile )
    

  if (initStatus.status === 'fail') {
    return { result: initStatus }
  }

  const commentBroadcastId = liveRecorder.broadcastId || liveRecorder.mediaId
  const commentCollector = (downloadComments && commentBroadcastId)
    ? await collectLiveComments(insta, commentBroadcastId, Date.now(), outputRecordPath, commentInterval, verbose, liveRecorder.username || username)
    : null
  verbose && console.log(`Username: ${liveRecorder.username}`)
  verbose && console.log(`User id: ${liveRecorder.userId}`)
  verbose && console.log(`Media id: ${liveRecorder.mediaId}`)
  verbose && console.log(`Comment broadcast id: ${commentBroadcastId || 'unavailable'}`)
  verbose && console.log(`First segment: ${liveRecorder.firstSegment}`)
  let commentsSaved = false
  const saveComments = async () => {
    if (commentCollector && !commentsSaved) {
      commentsSaved = true
      await commentCollector.stop()
    }
  }

  const result = makeRecords(liveRecorder, tryToFetchBegining, leaveTemp, verbose)
    .then(async (records) => {
      if (!records.startTime) {
        console.log(records)
        throw new Error('Something went wrong')
      }

      // Persist comments as soon as the captured media streams have been
      // closed, before ffmpeg muxing. Thus an ffmpeg error cannot discard them.
      await saveComments()

      try {
        const merged = await mergeFiles({ ...records, outputFile: outputRecordPath, ffmpegOutputOptions, verbose })
        if (!leaveTemp) {
          await rm(records.videoPath, { force: true })
          await rm(records.audioPath, { force: true })
        }
        return { ...merged, partial: Boolean(records.partial) }
      } catch (error) {
        console.error(`[Save] MP4 mux failed; partial media files were retained. ${error.message}`)
        return {
          status: 'partial',
          message: 'Recording was stopped and the MP4 could not be finalized. Partial video/audio files and comments were saved.',
          videoPath: records.videoPath,
          audioPath: records.audioPath,
          outputFile: outputRecordPath,
        }
      }
    })
    .catch(async (error) => {
      try { await saveComments() } catch (saveError) {
        console.error(`[Comments] Could not save comments: ${saveError.message}`)
      }
      throw error
    })
    .finally(() => clearTimeout(fixTimeout))
  
  return {
    result,
    saveAndExitSignal,
  }  
}

function mergeFiles({ videoPath, audioPath, outputFile, ffmpegOutputOptions, verbose }) {
  let showProgress = () => {}
  if (verbose) {
    showProgress = (progress) => {
      process.stdout.write(ansiEscapes.eraseLines(1) + `Ffmpeg processing: ${progress?.percent?.toFixed(2) ?? 100}% done`)
    }    
  }
  return new Promise((resolve, reject) => {
    ffmpeg()
      .input(videoPath)
      .input(audioPath)
      .outputOptions(ffmpegOutputOptions || [
        '-c:v copy',
        '-c:a aac'
      ])
      .on('progress', showProgress)
      .on('end', () =>   {
        verbose && console.log('\nFfmpeg processing has been finished')
        resolve({
          outputFile,
          status: 'success'
        })
      })
      .on('error', (err) => reject(err))      
      .save(outputFile)
  })
}
