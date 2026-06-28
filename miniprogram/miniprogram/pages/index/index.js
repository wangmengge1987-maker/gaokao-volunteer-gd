Page({
  onShareAppMessage() {
    return {
      title: '广东高考志愿助手 - 智能推荐冲/稳/保志愿',
      path: '/pages/index/index',
    };
  },

  goIntake() {
    wx.navigateTo({ url: '/pages/intake/intake' });
  },
});
