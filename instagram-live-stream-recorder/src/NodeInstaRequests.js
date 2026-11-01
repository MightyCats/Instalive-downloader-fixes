import fetch from 'node-fetch'

export default class NodeInstaRequests {
  constructor({ csrfToken, xmlParser, sessionId, agent, cookieString }) {
    this.cookies = cookieString
    this.cookieMap = new Map(String(cookieString || '').split(';').map(part => {
      const index = part.indexOf('=')
      return index > 0 ? [part.slice(0, index).trim(), part.slice(index + 1).trim()] : ['', '']
    }).filter(([name]) => name))
    const cookieCsrf = cookieString
      ? (cookieString.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] || '')
      : ''
    this.csrfToken = cookieCsrf || csrfToken
    const cookieSession = cookieString
      ? (cookieString.match(/(?:^|;\s*)sessionid=([^;]+)/)?.[1] || '')
      : ''
    this.sessionId = cookieSession || sessionId
    this.xIgWWWClaim = '0'
    this.xmlParser = xmlParser
    this.xIgAppId = '936619743392459'
    this.agent = agent // Proxy agent only; never use this as User-Agent.
    this.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    this._syncCookieFields()
  }

  _syncCookieFields() {
    this.cookies = [...this.cookieMap.entries()].map(([name, value]) => `${name}=${value}`).join('; ')
    this.csrfToken = this.cookieMap.get('csrftoken') || this.csrfToken
    this.sessionId = this.cookieMap.get('sessionid') || this.sessionId
  }

  _handleHeaders(...headers) {
    for (const [header, value] of headers) {
      if (String(header).toLowerCase() === 'x-ig-set-www-claim') {
        this.xIgWWWClaim = value
      }
    }
  }

  _absorbResponseCookies(response) {
    // Match requests.Session behavior: retain cookies Instagram legitimately
    // refreshes during a session, rather than sending a stale startup snapshot.
    const raw = response?.headers?.raw?.()
    const setCookies = raw?.['set-cookie'] || []
    for (const entry of setCookies) {
      const pair = String(entry).split(';', 1)[0]
      const index = pair.indexOf('=')
      if (index <= 0) continue
      const name = pair.slice(0, index).trim()
      const value = pair.slice(index + 1).trim()
      if (name && value) this.cookieMap.set(name, value)
    }
    if (setCookies.length) this._syncCookieFields()
  }

  _webRequestHeaders(username = '') {
    const cleanUsername = String(username || '').trim().replace(/^@/, '')
    return {
      'User-Agent': this.userAgent,
      'Accept': 'application/json, text/plain, */*',
      'Accept-Language': 'en-US,en;q=0.9',
      'Sec-CH-UA': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
      'Sec-CH-UA-Mobile': '?0',
      'Sec-CH-UA-Platform': '"Windows"',
      'X-IG-App-ID': this.xIgAppId,
      'X-ASBD-ID': '359341',
      'X-CSRFToken': this.csrfToken,
      'X-IG-WWW-Claim': this.xIgWWWClaim,
      'X-Requested-With': 'XMLHttpRequest',
      'Cookie': this.cookies || `sessionid=${this.sessionId}; csrftoken=${this.csrfToken};`,
      'Origin': 'https://www.instagram.com',
      'Referer': `https://www.instagram.com/${cleanUsername ? cleanUsername + '/' : ''}`
    }
  }

  async getUsernameInfo(username) {
    if (!this.csrfToken) {
      throw new Error('Error: csrfToken is requered for getUsernameInfo request')
    }

    const cookieHeader =
      this.cookies ||
      `sessionid=${this.sessionId}; csrftoken=${this.csrfToken};`

    const webHeaders = {
      "accept": "*/*",
      "accept-language": "en-US,en;q=0.9",
      "x-asbd-id": "359341",
      "x-csrftoken": this.csrfToken,
      "x-ig-app-id": "936619743392459",
      "x-ig-www-claim": this.xIgWWWClaim,
      "cookie": cookieHeader,
      "User-Agent": this.userAgent,
      "Referer": "https://www.instagram.com/",
      "Referrer-Policy": "strict-origin-when-cross-origin"
    }

    const mobileHeaders = {
      ...webHeaders,
      "X-IG-App-ID": "567067343352427",
      "X-IG-Connection-Type": "WIFI",
      "X-FB-HTTP-Engine": "Liger",
      "Accept-Language": "en-US",
      "Accept-Encoding": "gzip, deflate",
      "Connection": "close",
      "User-Agent":
        "Instagram 237.0.0.14.102 Android (25/7.1.2; 320dpi; 720x1280; samsung; SM-G973N; aosp; android_x86; en_US; 373310563)"
    }

    const normalizeUser = (user, fallbackUsername = username) => {
      if (!user || typeof user !== 'object') return null
      const userId = user.pk ?? user.id ?? user.user_id
      if (!userId) return null

      const result = {
        ...user,
        id: String(userId),
        pk: userId
      }
      if (!result.username && fallbackUsername) result.username = fallbackUsername
      return result
    }

    const findUser = (value) => {
      if (!value) return null

      if (Array.isArray(value)) {
        for (const item of value) {
          const found = findUser(item)
          if (found) return found
        }
        return null
      }

      if (typeof value !== 'object') return null

      // Prefer an exact username match when the endpoint returns multiple users.
      const candidate = value.username
      if (typeof candidate === 'string' &&
          candidate.toLowerCase() === username.toLowerCase()) {
        const normalized = normalizeUser(value)
        if (normalized) return normalized
      }

      for (const [key, child] of Object.entries(value)) {
        // Avoid treating arbitrary numeric fields as users.
        if (key === 'pk' || key === 'id' || key === 'user_id') continue
        const found = findUser(child)
        if (found) return found
      }
      return null
    }

    const makeResult = (user, status = 200) => {
      const normalized = normalizeUser(user)
      if (!normalized) return null
      return {
        ok: true,
        status,
        json: {
          data: {
            user: normalized
          }
        }
      }
    }

    const readJson = async (response) => {
      try {
        return await response.json()
      } catch (_) {
        return null
      }
    }

    const tryFeed = async () => {
      // IMPORTANT:
      // The www.instagram.com feed/user/{username}/username/ endpoint is
      // currently the most useful fallback for accounts for which
      // web_profile_info returns HTTP 400.
      const urls = [
        `https://www.instagram.com/api/v1/feed/user/${encodeURIComponent(username)}/username/?count=1`,
        `https://i.instagram.com/api/v1/feed/user/${encodeURIComponent(username)}/username/?count=1`
      ]

      for (const url of urls) {
        try {
          const response = await fetch(url, {
            headers: webHeaders,
            method: 'GET',
            agent: this.agent
          })

          if (!response.ok) {
            const text = await response.text().catch(() => '')
            console.warn(`username feed ${response.status}: ${text.slice(0, 200)}`)
            continue
          }

          this._handleHeaders(...response.headers)
          const data = await readJson(response)
          if (!data) continue

          // Common response shapes, including items[].user.
          const directUser =
            data?.user ||
            data?.data?.user ||
            data?.graphql?.user

          const user = normalizeUser(directUser) || findUser(data)

          if (user) {
            console.log(`[I] Instagram user resolved by username feed: ${username} -> ${user.id}`)
            return makeResult(user, response.status)
          }
        } catch (error) {
          console.warn(`username feed failed for ${username}: ${error.message}`)
        }
      }
      return null
    }

    const tryProfilePage = async () => {
      try {
        const url = `https://www.instagram.com/${encodeURIComponent(username)}/`
        const response = await fetch(url, {
          headers: {
            ...webHeaders,
            "X-Requested-With": "XMLHttpRequest",
            "X-Asbd-Id": "359341",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document"
          },
          method: 'GET',
          agent: this.agent
        })

        if (!response.ok) return null

        const text = await response.text()
        const patterns = [
          /"profilePage_(\d+)"/i,
          /"user_id"\s*:\s*"?(\d+)"?/i,
          new RegExp(
            `"pk"\\s*:\\s*"?([0-9]+)"?[^{}]{0,500}?"username"\\s*:\\s*"${username.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"`,
            'i'
          ),
          new RegExp(
            `"id"\\s*:\\s*"?([0-9]+)"?[^{}]{0,500}?"username"\\s*:\\s*"${username.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"`,
            'i'
          )
        ]

        for (const pattern of patterns) {
          const match = text.match(pattern)
          if (match) {
            const user = normalizeUser({ id: match[1], pk: match[1], username })
            if (user) {
              console.log(`[I] Instagram user resolved from profile page: ${username} -> ${user.id}`)
              return makeResult(user, response.status)
            }
          }
        }
      } catch (error) {
        console.warn(`profile page lookup failed for ${username}: ${error.message}`)
      }
      return null
    }

    const trySearch = async () => {
      try {
        const response = await fetch(
          `https://i.instagram.com/api/v1/users/search/?timezone_offset=0&q=${encodeURIComponent(username)}&count=30`,
          {
            headers: mobileHeaders,
            method: 'GET',
            agent: this.agent
          }
        )

        if (!response.ok) return null

        const data = await readJson(response)
        if (!data || data.status === 'fail' || !Array.isArray(data.users)) return null

        const wanted = username.toLowerCase()
        const user = data.users
          .map(item => normalizeUser(item))
          .find(item => item && typeof item.username === 'string' &&
                item.username.toLowerCase() === wanted)

        if (user) {
          console.log(`[I] Instagram user resolved by user search: ${username} -> ${user.id}`)
          return makeResult(user, response.status)
        }
      } catch (error) {
        console.warn(`user search failed for ${username}: ${error.message}`)
      }
      return null
    }

    const tryUsernameInfo = async () => {
      const url =
        `https://i.instagram.com/api/v1/users/${encodeURIComponent(username)}/usernameinfo/`

      // POST is used first, with GET retained for older Instagram behavior.
      try {
        const form = new URLSearchParams()
        form.set('_csrftoken', this.csrfToken)

        const uidMatch = cookieHeader.match(/(?:^|;\s*)ds_user_id=([^;]*)/)
        if (uidMatch) form.set('_uid', uidMatch[1])

        const uuidMatch = cookieHeader.match(/(?:^|;\s*)(?:ig_uuid|uuid)=([^;]*)/)
        if (uuidMatch) form.set('_uuid', uuidMatch[1])

        const response = await fetch(url, {
          headers: {
            ...mobileHeaders,
            "content-type": "application/x-www-form-urlencoded"
          },
          method: 'POST',
          body: form.toString(),
          agent: this.agent
        })

        if (response.ok) {
          this._handleHeaders(...response.headers)
          const data = await readJson(response)
          const user = findUser(data)
          if (user) return makeResult(user, response.status)
        }
      } catch (error) {
        console.warn(`usernameinfo POST failed for ${username}: ${error.message}`)
      }

      try {
        const response = await fetch(url, {
          headers: mobileHeaders,
          method: 'GET',
          agent: this.agent
        })

        if (response.ok) {
          this._handleHeaders(...response.headers)
          const data = await readJson(response)
          const user = findUser(data)
          if (user) return makeResult(user, response.status)
        }
      } catch (error) {
        console.warn(`usernameinfo GET failed for ${username}: ${error.message}`)
      }

      return null
    }

    // Resolver order is deliberate:
    // 1. username feed (the workaround that bypasses web_profile_info 400)
    // 2. profile HTML
    // 3. mobile user search
    // 4. usernameinfo POST/GET
    // 5. web_profile_info only as a last resort
    for (const resolver of [tryFeed, tryProfilePage, trySearch, tryUsernameInfo]) {
      const result = await resolver()
      if (result) return result
    }

    try {
      const profileUrl =
        `https://www.instagram.com/api/v1/users/web_profile_info/?username=${encodeURIComponent(username)}`
      const response = await fetch(profileUrl, {
        headers: webHeaders,
        method: 'GET',
        agent: this.agent
      })

      if (response.ok) {
        this._handleHeaders(...response.headers)
        const data = await readJson(response)
        const user = findUser(data)
        if (user) return makeResult(user, response.status)
      } else {
        const text = await response.text().catch(() => '')
        console.warn(`web_profile_info ${response.status}: ${text.slice(0, 300)}`)
      }
    } catch (error) {
      console.warn(`web_profile_info failed for ${username}: ${error.message}`)
    }

    return {
      ok: false,
      status: 0,
      error: `Unable to resolve Instagram user: ${username}`
    }
  }

  getStreamInfo(userId) {
    if (!this.csrfToken) {
      throw new Error('Error: csrfToken is requered for getStreamInfo request')
    }

    if (!this.sessionId) {
      throw new Error('Error: sessionId is requered for getStreamInfo request')
    }

    return fetch(`https://i.instagram.com/api/v1/live/web_info/?target_user_id=${userId}`, {
      "headers": {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,ru;q=0.8",
        "sec-ch-ua": "\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"102\", \"Google Chrome\";v=\"102\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "x-asbd-id": "198387",
        "User-Agent": this.userAgent,
        "x-csrftoken": this.csrfToken,
        "x-ig-app-id": this.xIgAppId,
        "x-ig-www-claim": this.xIgWWWClaim,
        "cookie": this.cookies || `sessionid=${this.sessionId}; csrftoken=${this.csrfToken};`,
        "Referer": "https://www.instagram.com/",
        "Referrer-Policy": "strict-origin-when-cross-origin"
      },
      "body": null,
      "method": "GET",
      agent: this.agent
    }).then(async (response) => {
      if (!response.ok) {
        return {
            ok: false,
            status: response.status,
        }
      }
      this._handleHeaders(...response.headers)
      this._absorbResponseCookies(response)
      return {
          ok: true,
          status: response.status,
          json: await response.json(),
      }
    })
  }


  async getLiveComments(broadcastId, lastCommentTs = 0, username = '') {
    if (!broadcastId) {
      return { ok: false, status: 0, error: 'Live broadcast ID is missing' }
    }

    const params = new URLSearchParams({
      last_comment_ts: String(lastCommentTs || 0),
      comment_count: '150',
      encoding_tag: 'instagram_live_comments'
    })
    const url = `https://www.instagram.com/api/v1/live/${encodeURIComponent(broadcastId)}/get_comment/?${params}`

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: this._webRequestHeaders(username),
        agent: this.agent,
        timeout: 10000
      })
      this._handleHeaders(...response.headers)
      this._absorbResponseCookies(response)
      const text = await response.text()
      let json
      try {
        json = JSON.parse(text)
      } catch (_) {
        const contentType = response.headers?.get?.('content-type') || ''
        const isHtml = /text\/html/i.test(contentType) || /^\s*<!doctype html|^\s*<html/i.test(text)
        const kind = isHtml
          ? 'Instagram returned an HTML page instead of comment JSON (login/checkpoint/anti-automation page).'
          : 'Instagram returned a non-JSON comments response.'
        return { ok: false, status: response.status, blocked: isHtml, error: `${kind} HTTP ${response.status}` }
      }

      if (!response.ok || json?.status === 'fail') {
        const message = json?.message || `Comments request failed: HTTP ${response.status}`
        return {
          ok: false,
          status: response.status,
          blocked: response.status === 401 || response.status === 403 || response.status === 429 || /challenge|checkpoint|login_required/i.test(String(message)),
          error: message
        }
      }
      if (!json || typeof json !== 'object' || !Array.isArray(json.comments)) {
        return { ok: false, status: response.status, error: 'Comments response JSON did not contain a comments array.' }
      }
      return { ok: true, status: response.status, json }
    } catch (error) {
      return { ok: false, status: 0, error: error.message }
    }
  }

  getMpd(mpdUrl) {
    return fetch(mpdUrl, {
      "headers": {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,ru;q=0.8",
        "sec-ch-ua": "\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"102\", \"Google Chrome\";v=\"102\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "Referer": "https://www.instagram.com/",
        "Referrer-Policy": "strict-origin-when-cross-origin"
      },
      "body": null,
      "method": "GET",
      agent: this.agent
    }).then(async (response) => {
      if (!response.ok) {
        return {
            ok: false,
            status: response.status
        }
      }
      this._handleHeaders(...response.headers)
      const text = await response.text()
      return {
          ok: true,
          status: response.status,
          xml: this.xmlParser.parseFromString(text, "application/xml")
      }
    })
  }

  async getSegment(segmentUrl, n = 5) {
    const response = await fetch(segmentUrl, {
      "headers": {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,ru;q=0.8",
        "sec-ch-ua": "\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"102\", \"Google Chrome\";v=\"102\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "Referer": "https://www.instagram.com/",
        "Referrer-Policy": "strict-origin-when-cross-origin"
      },
      "body": null,
      "method": "GET",
      agent: this.agent,
    }).catch((error) => {
      console.error(error);
      return false;
    });
    if (!response || !response.ok) {
      if (n === 0) {
        return {
          ok: false,
          status: response.status,
        };
      };
      console.info("retrying...", n, response.status, response.statusText);
      return await this.getSegment(segmentUrl, n - 1);
    }
    this._handleHeaders(...response.headers);
    return {
      ok: true,
      status: response.status,
      blob: await response.blob(),
    };
  }

  downloadVideoSegment() {
    throw Error('call initializeVideoDownloader(videoUrlTemplate) first')
  }

  downloadAudioSegment() {
    throw Error('call initializeAudioDownloader(audioUrlTemplate) first')
  }

  initializeVideoDownloader(videoUrlTemplate) {
    const downloadVideoSegment = function(segment) {
      return this.getSegment(videoUrlTemplate.replace(/\$Time\$/, segment))
    }

    this.downloadVideoSegment = downloadVideoSegment.bind(this)
    return this
  }

  initializeAudioDownloader(audioUrlTemplate) {
    const downloadAudioSegment = function(segment) {
      return this.getSegment(audioUrlTemplate.replace(/\$Time\$/, segment))
    }

    this.downloadAudioSegment = downloadAudioSegment.bind(this)
    return this
  }
}