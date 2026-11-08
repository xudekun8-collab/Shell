App({
  globalData: {
    userId: '',
    launchAt: 0,
  },

  onLaunch() {
    this.globalData.launchAt = Date.now();
    this._clearExpiredGreetings();
  },

  _clearExpiredGreetings() {
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    try {
      const info = wx.getStorageInfoSync();
      (info.keys || []).forEach((key) => {
        const m = /^greeting_(\d{4})(\d{2})(\d{2})_/.exec(key);
        if (!m) return;
        const date = new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
        if (date.getTime() < cutoff) {
          wx.removeStorageSync(key);
        }
      });
    } catch (err) {
      console.error('清理过期问候缓存失败：', err);
    }
  },

  onError(err) {
    console.error('小程序运行时错误：', err);
  },
});
