import { recordLiveStream } from './src/recordLiveStream.js'
import { handleOptions } from './src/optionHandler.js'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'url'
import { dirname } from 'path'
import path from 'path'

async function main () {
  const options = await handleOptions()
  const baseDir = 'e:\\work\\instagram'
  await mkdir(path.join(baseDir), { recursive: true })
  await mkdir(path.join(baseDir, 'Temp'), { recursive: true })
  options.verbose && console.log(options)
  const { result, saveAndExitSignal } = await recordLiveStream(options)
 
  function saveAndExit () {
    console.log('SIGINT')
    console.log('THe application will save records and exit. If you want to exit process immediately, send SIGINT one more time.')
    saveAndExitSignal()
    process.off('SIGINT', saveAndExit)
  }
  process.on('SIGINT', saveAndExit)

  return result
}

main().then((result) =>  {
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
}).catch((err) => console.log(err))