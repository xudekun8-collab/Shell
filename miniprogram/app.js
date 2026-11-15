const TTS_CACHE_PREFIX = 'tts_cache_';
const TTS_CACHE_KEEP = 40;
const TTS_CACHE_MAX_AGE = 3 * 24 * 60 * 60 * 1000;

App({
  globalData: {
    userId: '',
    launchAt: 0,
    pendingGame: null,
    showGameMenu: false,
    online: true,
  },

  onLaunch() {
    this.globalData.launchAt = Date.now();
    this._initPrivacy();
    this._clearExpiredGreetings();
    this._watchNetwork();
    this._cleanTtsCache();
  },

  // 麦克风属于隐私接口：小程序后台声明「用户隐私保护指引」后，
  // 首次调用录音前微信会回调这里，必须由我们弹窗并明确 resolve 同意/拒绝，
  // 否则 wx.getRecorderManager().start() 在真机上直接失败且没有提示。
  _initPrivacy() {
    if (typeof wx.onNeedPrivacyAuthorization !== 'function') return;
    wx.onNeedPrivacyAuthorization((resolve) => {
      wx.showModal({
        title: '用麦克风前想跟您说一句',
        content: '您说的话会先转成文字，录音不保存。同意后才能用语音，不同意也能打字。',
        confirmText: '同意',
        cancelText: '不同意',
        success: (res) => {
          resolve({ event: res.confirm ? 'agree' : 'disagree' });
        },
        fail: () => resolve({ event: 'disagree' }),
      });
    });
  },

  // 网络状态全局维护，request.js 据此在离线时立即失败，不再逐次等超时
  _watchNetwork() {
    try {
      wx.getNetworkType({
        success: (res) => {
          this.globalData.online = res.networkType !== 'none';
        },
      });
      wx.onNetworkStatusChange((res) => {
        const wasOnline = this.globalData.online;
        this.globalData.online = !!res.isConnected;
        if (wasOnline && !res.isConnected) {
          wx.showToast({ title: '现在没网了，等会儿再试', icon: 'none' });
        }
      });
    } catch (err) {
      console.error('监听网络状态失败：', err);
    }
  },

  // 语音合成的 mp3 会写在 USER_DATA_PATH（上限 10MB），按时间与数量双维度清理
  _cleanTtsCache() {
    if (!wx.getFileSystemManager || !wx.env || !wx.env.USER_DATA_PATH) return;
    const fs = wx.getFileSystemManager();
    const root = wx.env.USER_DATA_PATH;
    const cutoff = Date.now() - TTS_CACHE_MAX_AGE;
    try {
      const names = (fs.readdirSync(root) || []).filter(
        (name) => name.indexOf(TTS_CACHE_PREFIX) === 0
      );
      const files = names.map((name) => {
        const path = root + '/' + name;
        let mtime = 0;
        try {
          mtime = (fs.statSync(path).lastModifiedTime || 0) * 1000;
        } catch (err) {
          mtime = 0;
        }
        return { path, mtime };
      });
      files.sort((a, b) => b.mtime - a.mtime);
      files.forEach((file, index) => {
        if (index < TTS_CACHE_KEEP && file.mtime >= cutoff) return;
        try {
          fs.unlinkSync(file.path);
        } catch (err) {
          console.warn('删除语音缓存失败：', file.path, err);
        }
      });
    } catch (err) {
      console.error('清理语音缓存失败：', err);
    }
  },

  _clearExpiredGreetings() {
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    try {
      const info = wx.getStorageInfoSync();
      (info.keys || []).forEach((key) => {
        const current = /^greeted_.*_(\d{4})(\d{2})(\d{2})$/.exec(key);
        const legacy = /^greeting_(\d{4})(\d{2})(\d{2})_/.exec(key);
        const m = current || legacy;
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

  onUnhandledRejection(res) {
    console.error('未处理的 Promise 异常：', res && res.reason);
  },
});
