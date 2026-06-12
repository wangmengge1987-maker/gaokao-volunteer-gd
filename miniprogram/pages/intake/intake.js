const api = require('../../utils/api');

Page({
  data: {
    subjectTrack: '物理',
    rechoiceOptions: ['化学', '生物', '政治', '地理'],
    rechoices: ['化学', '生物'],
    score: '',
    cities: '',
    majors: '',
    loading: false,
  },

  onTrackChange(e) {
    this.setData({ subjectTrack: e.detail.value });
  },

  onRechange(e) {
    this.setData({ rechoices: e.detail.value });
  },

  onScoreInput(e) {
    this.setData({ score: e.detail.value });
  },

  onCitiesInput(e) {
    this.setData({ cities: e.detail.value });
  },

  onMajorsInput(e) {
    this.setData({ majors: e.detail.value });
  },

  async submit() {
    const { subjectTrack, rechoices, score, cities, majors } = this.data;
    if (!score) {
      wx.showToast({ title: '请输入分数', icon: 'none' });
      return;
    }
    if (rechoices.length !== 2) {
      wx.showToast({ title: '再选科目须选 2 门', icon: 'none' });
      return;
    }

    this.setData({ loading: true });
    try {
      const preferences = {};
      if (cities.trim()) {
        preferences.cities = cities.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
      }
      if (majors.trim()) {
        preferences.majors = majors.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
      }

      const result = await api.recommend({
        score: Number(score),
        subject_track: subjectTrack,
        rechoices,
        preferences,
      });

      getApp().globalData.lastResult = result;
      wx.navigateTo({ url: '/pages/result/result' });
    } catch (err) {
      wx.showToast({
        title: (err && err.detail) || '请求失败，请检查后端',
        icon: 'none',
      });
    } finally {
      this.setData({ loading: false });
    }
  },
});
