Page({
  data: { result: null },

  onShow() {
    const result = getApp().globalData.lastResult;
    this.setData({ result });
  },

  goChat(e) {
    const index = e.currentTarget.dataset.index;
    wx.navigateTo({ url: `/pages/chat/chat?index=${index}` });
  },
});
