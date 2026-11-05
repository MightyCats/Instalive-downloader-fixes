import { recordLiveStream } from './src/recordLiveStream.js'
import { handleOptions } from './src/optionHandler.js'

async function main () {
  const options = await handleOptions()
  options.verbose && console.log(options)

  const { result, saveAndExitSignal } = await recordLiveStream(options)

  let stopping = false
  function saveAndExit () {
    if (stopping) {
      console.warn('[Save] Shutdown is already in progress. Please wait for the files to be saved.')
      return
    }
    stopping = true
    console.log('\\n[Save] Ctrl+C detected. Stopping the recording and saving the video/comments. Please wait...')
    // Keep the process alive while the recorder closes its streams and saves
    // comments and the MP4 (or retains the partial media files).
    saveAndExitSignal().catch((error) => {
      console.error(`[Save] Could not stop recording cleanly: ${error.message}`)
    })
  }
  process.on('SIGINT', saveAndExit)

  return result
}

main().then((result) => {
  if (result.status === 'success') {
    console.log(result.outputFile)
    if (result.partial) {
      console.log('[Save] Partial recording was finalized as an MP4 after cancellation.')
    }
  } else {
    console.log(result.message)
    if (result.videoPath) console.log(`[Save] Partial video: ${result.videoPath}`)
    if (result.audioPath) console.log(`[Save] Partial audio: ${result.audioPath}`)
  }
  process.exit(0)
}).catch((err) => {
  console.error(err)
  process.exitCode = 1
})
