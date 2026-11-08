const config = require('./config.js');

let _redirecting = false;

function token() {
  return wx.getStorageSync('token') || '';
}

function handleUnauthorized() {
  wx.removeStorageSync('token');
  wx.removeStorageSync('user_id');
  if (_redirecting) return;
  _redirecting = true;
  wx.showToast({ title: '再进一次就好', icon: 'none' });
  wx.redirectTo({
    url: '/pages/login/login',
    complete() {
      _redirecting = false;
    },
  });
}

function doRequest(options) {
  const method = (options.method || 'GET').toUpperCase();
  const timeoutMs = options.timeout || (method === 'GET' ? 8000 : 15000);
  return new Promise((resolve) => {
    wx.request({
      url: config.base_url + options.url,
      method: method,
      data: options.data || {},
      timeout: timeoutMs,
      header: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token(),
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve({ ok: true, data: res.data, status: res.statusCode });
        } else if (res.statusCode === 401 && !options.skipAuthRedirect) {
          handleUnauthorized();
          resolve({ ok: false, msg: '登录已失效', status: 401 });
        } else {
          resolve({ ok: false, msg: '我这儿信号有点弱，咱们等会儿再说。', status: res.statusCode });
        }
      },
      fail(err) {
        console.error('wx.request fail:', err.errMsg);
        const kind = err.errMsg && err.errMsg.indexOf('timeout') >= 0 ? 'timeout' : 'network';
        resolve({ ok: false, msg: '我这儿信号有点弱，咱们等会儿再说。', kind: kind });
      },
    });
  });
}

function request(options) {
  const method = (options.method || 'GET').toUpperCase();
  return doRequest(options).then((res) => {
    const shouldRetry = method === 'GET' && !res.ok && res.kind === 'network';
    if (!shouldRetry) return res;
    return new Promise((resolve) => {
      setTimeout(() => doRequest(options).then(resolve), 800);
    });
  });
}

module.exports = { request };
