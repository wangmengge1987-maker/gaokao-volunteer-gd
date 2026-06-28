const api = require('../../utils/api');

Page({
  data: {
    volunteer: null,
    question: '',
    explanation: '',
    loading: false,
  },

  onShareAppMessage() {
    return {
      title: '广东高考志愿助手 - AI 解读志愿详情',
      path: '/pages/index/index',
    };
  },

  onLoad(options) {
    const result = getApp().globalData.lastResult;
    const index = Number(options.index || 0);
    const volunteer = result && result.volunteers ? result.volunteers[index] : null;
    this.setData({ volunteer });
    if (volunteer) {
      this.fetchExplain();
    }
  },

  onQuestion(e) {
    this.setData({ question: e.detail.value });
  },

  async fetchExplain() {
    const { volunteer, question } = this.data;
    if (!volunteer) return;
    this.setData({ loading: true });
    try {
      const res = await api.explain(volunteer, question || undefined);
      this.setData({ explanation: res.explanation });
    } catch (err) {
      wx.showToast({ title: '解释失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  ask() {
    this.fetchExplain();
  },
});
