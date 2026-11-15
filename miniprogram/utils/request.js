const config = require('./config.js');

const FRIENDLY_NETWORK = '我这儿信号有点弱，咱们等会儿再说。';
const FRIENDLY_OFFLINE = '现在没网了，等有网咱们再聊';
const FRIENDLY_SERVER = '我这儿有点卡，等会儿再说';

let _redirecting = false;

function token() {
  return wx.getStorageSync('token') || '';
}

// 全局网络状态由 app.js 维护，离线时直接失败，避免每个请求都等超时
function online() {
  try {
    const app = getApp();
    return !(app && app.globalData && app.globalData.online === false);
  } catch (err) {
    return true;
  }
}

function clearElderSession() {
  wx.removeStorageSync('token');
  wx.removeStorageSync('user_id');
  wx.removeStorageSync('thread_id');
  // 记录页的缓存是上一个账号的数据，换号时必须清掉，避免短暂串号
  wx.removeStorageSync('records_cache_v1');
  try {
    const info = wx.getStorageInfoSync();
    (info.keys || []).forEach((key) => {
      if (key.indexOf('chat_history_') === 0 || key.indexOf('greeted_') === 0) {
        wx.removeStorageSync(key);
      }
    });
  } catch (err) {
    console.error('清理老人本地会话失败：', err);
  }
}

function handleUnauthorized() {
  clearElderSession();
  if (_redirecting) return;
  _redirecting = true;
  wx.showToast({ title: '再进一次就好', icon: 'none' });
  wx.reLaunch({
    url: '/pages/login/login',
    complete() {
      _redirecting = false;
    },
  });
}

// 后端 4xx 的 detail 是中文提示，透传给调用方决定是否展示
function detailOf(data) {
  if (data && typeof data.detail === 'string') return data.detail;
  return '';
}

function doRequest(options) {
  const method = (options.method || 'GET').toUpperCase();
  const timeoutMs = options.timeout || (method === 'GET' ? 8000 : 15000);
  if (!online()) {
    return Promise.resolve({ ok: false, msg: FRIENDLY_OFFLINE, kind: 'offline' });
  }
  // authToken 显式传空串表示该请求不带鉴权（例如家属绑定）
  const authToken = options.authToken !== undefined ? options.authToken : token();
  const header = { 'Content-Type': 'application/json' };
  if (authToken) header.Authorization = 'Bearer ' + authToken;
  return new Promise((resolve) => {
    const payload = {
      url: config.baseUrl() + options.url,
      method: method,
      data: options.data || {},
      timeout: timeoutMs,
      header: header,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve({ ok: true, data: res.data, status: res.statusCode });
        } else if (res.statusCode === 401) {
          if (typeof options.onUnauthorized === 'function') {
            options.onUnauthorized();
          } else if (!options.skipAuthRedirect && options.authToken === undefined) {
            handleUnauthorized();
          }
          resolve({ ok: false, msg: '登录已失效', status: 401, kind: 'auth' });
        } else {
          // 4xx 多半是业务拒绝（邀请码失效、今天留过话了），后端 detail 是中文，
          // 直接用它当提示，不再一律说成「信号弱」；5xx 才算服务端问题。
          const detail = detailOf(res.data);
          const serverSide = res.statusCode >= 500;
          resolve({
            ok: false,
            msg: detail || (serverSide ? FRIENDLY_SERVER : FRIENDLY_NETWORK),
            status: res.statusCode,
            detail: detail,
            kind: serverSide ? 'server' : 'business',
          });
        }
      },
      fail(err) {
        console.error('wx.request fail:', err.errMsg);
        const kind = err.errMsg && err.errMsg.indexOf('timeout') >= 0 ? 'timeout' : 'network';
        resolve({ ok: false, msg: FRIENDLY_NETWORK, kind: kind });
      },
    };
    if (options.responseType) payload.responseType = options.responseType;
    wx.request(payload);
  });
}

function request(options) {
  const method = (options.method || 'GET').toUpperCase();
  return doRequest(options).then((res) => {
    // 离线不重试，避免白等两轮超时
    const shouldRetry =
      method === 'GET' && !res.ok && (res.kind === 'network' || res.kind === 'timeout');
    if (!shouldRetry) return res;
    return new Promise((resolve) => {
      setTimeout(() => doRequest(options).then(resolve), 800);
    });
  });
}

module.exports = {
  request,
  clearElderSession,
  FRIENDLY_NETWORK,
  FRIENDLY_OFFLINE,
  FRIENDLY_SERVER,
};
