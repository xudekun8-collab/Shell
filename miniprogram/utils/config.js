// 后端地址按微信运行环境切换，不再把局域网 IP 写死在调用处：
//   develop —— 开发者工具 / 真机调试，走局域网 http（需勾选「不校验合法域名」）
//   trial   —— 体验版，必须已备案域名 + 正式 HTTPS 证书
//   release —— 正式版，同上
// 交付前把 LAN_HOST 换成自己电脑的 IPv4，API_HOST 换成实际域名。
const LAN_HOST = '192.168.0.105:8000';
const API_HOST = 'api.example.com';

const BASE_URLS = {
  develop: 'http://' + LAN_HOST,
  trial: 'https://' + API_HOST,
  release: 'https://' + API_HOST,
};

const OVERRIDE_KEY = 'api_base';

// 微信运行环境：develop / trial / release。取不到时按开发环境处理。
function envVersion() {
  try {
    const info = wx.getAccountInfoSync();
    const version = info && info.miniProgram && info.miniProgram.envVersion;
    return version || 'develop';
  } catch (err) {
    return 'develop';
  }
}

// 本地应急覆盖：真机换网络时不必改代码重新编译，入口在登录页长按。
function readOverride() {
  try {
    return wx.getStorageSync(OVERRIDE_KEY) || '';
  } catch (err) {
    return '';
  }
}

function baseUrl() {
  return readOverride() || BASE_URLS[envVersion()] || BASE_URLS.develop;
}

function setApiBase(url) {
  const text = (url || '').trim();
  if (!text) {
    wx.removeStorageSync(OVERRIDE_KEY);
    return '';
  }
  const normalized = text.replace(/\/+$/, '');
  wx.setStorageSync(OVERRIDE_KEY, normalized);
  return normalized;
}

module.exports = {
  BASE_URLS,
  envVersion,
  baseUrl,
  setApiBase,
  OVERRIDE_KEY,
};
