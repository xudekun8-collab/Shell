function getUserId() {
  let userId = wx.getStorageSync('user_id');
  if (!userId) {
    userId = 'demo_user_1';
    wx.setStorageSync('user_id', userId);
  }
  return userId;
}

module.exports = { getUserId };
