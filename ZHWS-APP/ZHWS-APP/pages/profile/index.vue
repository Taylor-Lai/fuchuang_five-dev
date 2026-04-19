<template>
  <view class="page">
    <view class="user-card">
      <view class="avatar-wrap">
        <view class="avatar">
          <text class="avatar-text">头像</text>
        </view>
      </view>

      <view class="user-info">
        <text class="user-name">未登录</text>
        <text class="user-desc">登录后可同步历史记录、模板与个人数据</text>
      </view>

      <view class="login-btn" @tap="goLogin">
        <text class="login-btn-text">立即登录</text>
      </view>
    </view>

    <view class="panel stats-panel">
      <view class="stats-item">
        <text class="stats-num">0</text>
        <text class="stats-label">收藏</text>
      </view>
      <view class="stats-item">
        <text class="stats-num">0</text>
        <text class="stats-label">记录</text>
      </view>
      <view class="stats-item">
        <text class="stats-num">0</text>
        <text class="stats-label">模板</text>
      </view>
    </view>

    <view class="panel menu-panel">
      <view class="menu-item" @tap="showTip('请先登录')">
        <view class="menu-left">
          <text class="menu-icon">⭐</text>
          <text class="menu-text">我的收藏</text>
        </view>
        <text class="menu-arrow">></text>
      </view>

      <view class="menu-item" @tap="showTip('请先登录')">
        <view class="menu-left">
          <text class="menu-icon">🕘</text>
          <text class="menu-text">使用记录</text>
        </view>
        <text class="menu-arrow">></text>
      </view>

      <view class="menu-item" @tap="showTip('设置页待开发')">
        <view class="menu-left">
          <text class="menu-icon">⚙️</text>
          <text class="menu-text">设置</text>
        </view>
        <text class="menu-arrow">></text>
      </view>

      <view class="menu-item no-border" @tap="showTip('智汇文枢')">
        <view class="menu-left">
          <text class="menu-icon">ℹ️</text>
          <text class="menu-text">关于我们</text>
        </view>
        <text class="menu-arrow">></text>
      </view>
    </view>

    <view class="footer-tip">
      <text class="footer-text">登录后可体验完整的个人中心能力</text>
    </view>
  </view>
</template>

<script setup>
const goLogin = () => {
  uni.navigateTo({
    url: '/pages/auth/auth'
  })
}

const showTip = (title) => {
  uni.showToast({
    title,
    icon: 'none'
  })
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f6f8;
  padding: 24rpx;
  box-sizing: border-box;
}

.user-card {
  background: linear-gradient(135deg, #ffffff 0%, #f7f8fa 100%);
  border-radius: 28rpx;
  padding: 36rpx 28rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.05);
  margin-bottom: 24rpx;
}

.avatar-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
}

.avatar {
  width: 136rpx;
  height: 136rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #dfe7f1 0%, #cfd8e6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-text {
  font-size: 24rpx;
  color: #6b7280;
  font-weight: 600;
}

.user-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 28rpx;
}

.user-name {
  font-size: 40rpx;
  color: #111111;
  font-weight: 800;
  margin-bottom: 10rpx;
}

.user-desc {
  font-size: 24rpx;
  color: #7b7b7b;
  line-height: 1.7;
  text-align: center;
}

.login-btn {
  width: 100%;
  height: 88rpx;
  border-radius: 999rpx;
  background: #2dbe60;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-btn-text {
  font-size: 30rpx;
  color: #ffffff;
  font-weight: 700;
}

.panel {
  background: #ffffff;
  border-radius: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
  margin-bottom: 24rpx;
}

.stats-panel {
  display: flex;
  justify-content: space-between;
  padding: 24rpx 10rpx;
}

.stats-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stats-num {
  font-size: 36rpx;
  color: #111111;
  font-weight: 800;
  margin-bottom: 8rpx;
}

.stats-label {
  font-size: 24rpx;
  color: #7a7a7a;
}

.menu-panel {
  padding: 0 24rpx;
}

.menu-item {
  min-height: 96rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2rpx solid #f1f1f1;
}

.no-border {
  border-bottom: none;
}

.menu-left {
  display: flex;
  align-items: center;
}

.menu-icon {
  width: 40rpx;
  font-size: 30rpx;
  margin-right: 16rpx;
}

.menu-text {
  font-size: 28rpx;
  color: #1f1f1f;
}

.menu-arrow {
  font-size: 28rpx;
  color: #b5b5b5;
}

.footer-tip {
  padding: 8rpx 8rpx 40rpx;
  display: flex;
  justify-content: center;
}

.footer-text {
  font-size: 24rpx;
  color: #9a9a9a;
}
</style>