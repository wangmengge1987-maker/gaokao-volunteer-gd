Page({
  data: { result: null },

  onShareAppMessage() {
    return {
      title: '广东高考志愿助手 - 我的冲/稳/保志愿推荐',
      path: '/pages/index/index',
    };
  },

  onShow() {
    const result = getApp().globalData.lastResult;
    this.setData({ result });
  },

  goChat(e) {
    const index = e.currentTarget.dataset.index;
    wx.navigateTo({ url: `/pages/chat/chat?index=${index}` });
  },
});
