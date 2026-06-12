const { apiBase } = require('./config');

function request(path, method, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${apiBase}${path}`,
      method,
      data,
      header: { 'content-type': 'application/json' },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          reject(res.data || { message: `HTTP ${res.statusCode}` });
        }
      },
      fail: reject,
    });
  });
}

function lookupRank(subjectTrack, score) {
  return request('/api/v1/rank/lookup', 'POST', {
    subject_track: subjectTrack,
    score: Number(score),
  });
}

function recommend(payload) {
  return request('/api/v1/recommend', 'POST', payload);
}

function explain(volunteer, question) {
  return request('/api/v1/explain', 'POST', { volunteer, question });
}

module.exports = { lookupRank, recommend, explain };
