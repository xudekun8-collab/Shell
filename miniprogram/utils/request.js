const config = require('./config.js');

function request(options) {
  return new Promise((resolve) => {
    wx.request({
      url: config.base_url + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      timeout: 10000,
      header: { 'Content-Type': 'application/json' },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve({ ok: true, data: res.data });
        } else {
          resolve({ ok: false, msg: '我这儿信号有点弱，咱们等会儿再说。' });
        }
      },
      fail(err) {
        console.error('wx.request fail:', err.errMsg);
        resolve({ ok: false, msg: '我这儿信号有点弱，咱们等会儿再说。' });
      },
    });
  });
}

module.exports = { request };
