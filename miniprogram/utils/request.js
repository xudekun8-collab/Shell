const config = require('./config.js');

function doRequest(options) {
  const method = (options.method || 'GET').toUpperCase();
  // GET 都是本地数据库查询，8 秒足够；POST 要走大模型，才需要 15 秒
  const timeoutMs = options.timeout || (method === 'GET' ? 8000 : 15000);
  return new Promise((resolve) => {
    wx.request({
      url: config.base_url + options.url,
      method: method,
      data: options.data || {},
      timeout: timeoutMs,
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
    // 只对"连不上"重试；超时不重试——否则一次 8 秒会变成 16.8 秒还没反馈，老人会以为卡死
    const shouldRetry = method === 'GET' && !res.ok && res.kind === 'network';
    if (!shouldRetry) return res;
    return new Promise((resolve) => {
      setTimeout(() => doRequest(options).then(resolve), 800);
    });
  });
}

module.exports = { request };
