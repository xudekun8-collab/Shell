function getUserId() {
  return wx.getStorageSync('user_id') || '';
}

module.exports = { getUserId };
