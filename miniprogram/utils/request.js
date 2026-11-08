const config = require('./config.js');

function doRequest(options) {
  return new Promise((resolve) => {
    wx.request({
      url: config.base_url + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      timeout: 15000,
      header: { 'Content-Type': 'application/json' },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve({ ok: true, data: res.data, status: res.statusCode });
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
    const shouldRetry = method === 'GET' && !res.ok && (res.kind === 'network' || res.kind === 'timeout');
    if (!shouldRetry) return res;
    return new Promise((resolve) => {
      setTimeout(() => doRequest(options).then(resolve), 800);
    });
  });
}

module.exports = { request };
