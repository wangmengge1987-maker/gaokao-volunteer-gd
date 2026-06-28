Page({
  onShareAppMessage() {
    return {
      title: '广东高考志愿助手',
      path: '/pages/web/web',
    };
  },

  onMessage(e) {
    // 可选：监听 web-view 发来的消息
    console.log('web-view message:', e.detail);
  },
});