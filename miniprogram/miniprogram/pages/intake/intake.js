const api = require('../../utils/api');

Page({
  data: {
    subjectTrack: '物理',
    rechoiceOptions: ['化学', '生物', '政治', '地理'],
    rechoices: [],
    selectedMap: { '化学': false, '生物': false, '政治': false, '地理': false },
    score: '',
    rank: '',
    cities: '',
    cityFilter: 'prefer',
    cityCount: 0,
    majors: '',
    loading: false,
  },

  onShareAppMessage() {
    return {
      title: '广东高考志愿助手 - 输入分数，智能推荐志愿',
      path: '/pages/index/index',
    };
  },

  onTrackChange(e) {
    this.setData({ subjectTrack: e.detail.value });
  },

  toggleRechoice(e) {
    const value = e.currentTarget.dataset.value;
    let rechoices = [...this.data.rechoices];
    const idx = rechoices.indexOf(value);
    if (idx > -1) {
      rechoices.splice(idx, 1);
    } else {
      if (rechoices.length >= 2) {
        wx.showToast({ title: '最多选 2 门', icon: 'none' });
        return;
      }
      rechoices.push(value);
    }
    const selectedMap = {};
    const opts = ['化学', '生物', '政治', '地理'];
    opts.forEach(opt => { selectedMap[opt] = rechoices.indexOf(opt) > -1; });
    this.setData({ rechoices, selectedMap });
  },

  onScoreInput(e) {
    this.setData({ score: e.detail.value });
  },

  onRankInput(e) {
    this.setData({ rank: e.detail.value });
  },

  onCitiesInput(e) {
    const cities = e.detail.value;
    const cityList = cities.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    this.setData({ cities, cityCount: cityList.length });
  },

  onCityFilterChange(e) {
    this.setData({ cityFilter: e.detail.value });
  },

  onMajorsInput(e) {
    this.setData({ majors: e.detail.value });
  },

  async submit() {
    const { subjectTrack, rechoices, score, rank, cities, cityFilter, cityCount, majors } = this.data;
    if (!score) {
      wx.showToast({ title: '请输入分数', icon: 'none' });
      return;
    }
    if (!rank) {
      wx.showToast({ title: '请输入全省位次', icon: 'none' });
      return;
    }
    if (rechoices.length !== 2) {
      wx.showToast({ title: '再选科目须选 2 门', icon: 'none' });
      return;
    }

    // 2026年广东省本科录取最低分数线校验
    const BACHELOR_LINES = { '物理': 425, '历史': 440 };
    const line = BACHELOR_LINES[subjectTrack];
    if (Number(score) < line) {
      wx.showModal({
        title: '分数低于本科线',
        content: `该分数低于广东省本科普通类（${subjectTrack}）录取最低分数线（${line}分），因为数据库有限，无法对专科类学校生成志愿建议。`,
        showCancel: false,
      });
      this.setData({ loading: false });
      return;
    }

    this.setData({ loading: true });
    try {
      const cityList = cities.trim() ? cities.split(/[,，]/).map((s) => s.trim()).filter(Boolean) : [];
      if (cityFilter === 'strict' && cityList.length > 5) {
        wx.showToast({ title: '「仅限这些城市」模式最多 5 个城市', icon: 'none' });
        this.setData({ loading: false });
        return;
      }

      const preferences = {};
      if (cityList.length) preferences.cities = cityList;
      if (majors.trim()) {
        preferences.majors = majors.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
      }

      const result = await api.recommend({
        score: Number(score),
        rank: Number(rank),
        subject_track: subjectTrack,
        rechoices,
        preferences,
        city_filter: cityFilter,
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
