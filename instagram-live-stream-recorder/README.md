# instagram-live-stream-recorder Workaround

Unofficial compatibility fixes and improvements for Instagram LIVE recording.

This version includes a workaround for Instagram user-information API errors, browser-cookie authentication, live comment collection, JSON/SRT subtitle output, and safer recording cancellation.

## Features

- Workaround for Instagram `ig_business_category_subvertical` HTTP 400 errors.
- Username-based user-information retrieval.
- Instagram authentication using a browser-exported Netscape-format `cookies.txt` file.
- LIVE video and audio recording.
- Optional retrieval of earlier stream segments.
- Live comments saved in both JSON and SRT formats.
- Comment timestamps synchronized to the beginning of the recording.
- Partial recording preservation when recording is cancelled.
- Comments are saved before FFmpeg merges the video and audio.
- Temporary video/audio files are retained if final MP4 merging fails.

## Installation

1. Download or clone this repository.
2. Install the required Node.js dependencies:

```bash
npm install
```

3. Install FFmpeg and make sure it is available in your system PATH.
4. Edit `config.default.json` as described below.
5. Start recording using the normal command.

## Instagram Cookie Setup

An Instagram cookie file is required for authentication.

### 1. Export cookies from your browser

1. Log in to Instagram using Chrome or Firefox.
2. While logged in, export the cookies for `www.instagram.com` using a browser cookie-export extension.
3. Save the exported file in Netscape/Mozilla `cookies.txt` format.

The cookie file must contain at least these two cookies:

- `sessionid`
- `csrftoken`

### 2. Configure the cookie file path

Open `config.default.json` and set `cookiesFile` to the full path of your exported cookie file.

Example:

```json
{
  "proxy": "",
  "ffmpegOutputOptions": [
    "-c:v copy",
    "-c:a aac"
  ],
  "verbose": true,
  "full": true,
  "getFull": true,
  "leaveTemp": false,
  "downloadComments": true,
  "commentInterval": 5000,
  "cookiesFile": "C:/Program Files/Instagram-live-stream-recorder/www.instagram.com_cookies.txt"
}
```

Use forward slashes (`/`) in Windows paths, or escape backslashes (`\\`) in JSON strings.

The recorder reads the applicable Instagram cookies from this file and obtains the `sessionid` and `csrftoken` automatically.

If the cookie file cannot be read, or either required cookie is missing, recording will not start.

**Important:** Cookies are authentication credentials. Never upload your `cookies.txt` file to GitHub or share it with anyone. Do not include it in screenshots, logs, or issue reports.

## Download Location

The default recording directory is:

```text
E:\WORK\INSTAGRAM
```

Temporary video and audio files are stored in:

```text
E:\WORK\INSTAGRAM\Temp
```

### Change the default download directory

To change the default directory, update the directory setting in both files:

**1. `src/recordLiveStream.js`**

Find:

```javascript
const dirname = 'E:\\WORK\\INSTAGRAM'
```

Change it to your preferred directory. For example:

```javascript
const dirname = 'D:\\InstagramRecordings'
```

**2. `record.js`**

Find:

```javascript
const baseDir = 'e:\\work\\instagram'
```

Change it to the same directory:

```javascript
const baseDir = 'D:\\InstagramRecordings'
```

Make sure both paths are identical. The recorder creates the `Temp` directory under the selected base directory.

### Specify an output filename

The output filename can also be specified with the `-o` command-line option.

Example:

```bash
node record.js -u USERNAME -o "D:/InstagramRecordings/my_live.mp4"
```

The JSON and SRT comment files are created alongside the specified MP4 output file.

## Comment Download and Subtitle Files

Comment downloading is enabled by default.

The recorder periodically retrieves new comments while the LIVE stream is being recorded.

Default settings in `config.default.json`:

```json
{
  "downloadComments": true,
  "commentInterval": 5000
}
```

- `downloadComments`: Enables or disables comment collection.
- `commentInterval`: Comment polling interval in milliseconds. The default is 5000 ms (5 seconds).

### Output files

For a recording named:

```text
Instalive@USERNAME_YYYY-MM-DD.mp4
```

The recorder creates:

```text
Instalive@USERNAME_YYYY-MM-DD.mp4
Instalive@USERNAME_YYYY-MM-DD.json
Instalive@USERNAME_YYYY-MM-DD.chat.srt
```

**JSON file**

- Contains the original comment objects returned by Instagram.
- Uses a top-level `comments` array.
- Includes `total_elapsed`, the elapsed time in seconds from the beginning of the recording.
- Retains user information such as username and profile information when provided by Instagram.
- Compatible with the PyInstaLive-style JSON comment structure used by the MVD player.

**SRT file**

- Uses elapsed time synchronized with the recorded video.
- Displays the comment author's username and comment text.
- Each comment is displayed for 5 seconds.
- Uses the `.chat.srt` filename suffix.
- No TXT comment file is generated.

Example:

```text
1
00:00:10,000 --> 00:00:15,000
username: Hello!
```

### Disable comment downloading

To disable comment collection for one run:

```bash
node record.js -u USERNAME --no-comments
```

### Change the comment polling interval

For example, to poll every 8 seconds:

```bash
node record.js -u USERNAME --comment-interval 8000
```

## Recording and Cancellation

To start recording:

```bash
node record.js -u USERNAME --get-full --verbose
```

Press `Ctrl+C` once to request a safe stop.

The recorder will:

1. Stop recording.
2. Finish writing the captured video and audio streams.
3. Save the collected comments as JSON and SRT.
4. Attempt to merge the video and audio into an MP4 file.

If the recording is cancelled, the recorder attempts to finalize the captured portion as an MP4.

If FFmpeg merging fails, the partial video/audio files and comment files are retained where possible.

Pressing `Ctrl+C` a second time forces an immediate process exit. This may interrupt the saving process.

## Configuration Options

| Option | Description |
|---|---|
| `proxy` | Optional proxy server |
| `ffmpegOutputOptions` | FFmpeg output options |
| `verbose` | Enable detailed logging |
| `full` | Full recording option |
| `getFull` | Attempt to retrieve earlier stream segments |
| `leaveTemp` | Keep temporary files |
| `downloadComments` | Enable or disable comment collection |
| `commentInterval` | Comment polling interval in milliseconds |
| `cookiesFile` | Full path to the Instagram cookies.txt file |

## Troubleshooting

### Authentication error

- Check that the cookie file path is correct.
- Make sure the cookie file is in Netscape format.
- Confirm that it contains both `sessionid` and `csrftoken`.
- Export a fresh cookie file if the session has expired.

### Comments are not saved

- Confirm that `downloadComments` is set to `true`.
- Check the log for `[Comments]` messages.
- Instagram may temporarily reject comment requests or require an additional security check. Video recording may continue even if comment retrieval fails.

### MP4 file is not finalized

If FFmpeg merging fails, check the `Temp` folder for retained video and audio files. The comments are saved before the merge operation, so they may still be available as JSON and SRT.

## Important

This is an unofficial compatibility workaround for Instagram-side API changes.

Instagram's internal APIs may change without notice. The workaround may stop working if Instagram changes its endpoints or response formats.

## Security

Never publish or share:

- Instagram passwords
- `sessionid`
- `csrftoken`
- Authentication tokens
- Private cookies or authorization headers

Do not commit your personal `cookies.txt` file to GitHub.

## Original Project

[instagram-live-stream-recorder](https://github.com/vadimb88/instagram-live-stream-recorder)

This repository is not affiliated with Instagram, Meta, or the original project developer.
