<template>
  <view class="page">
    <view class="header">
      <text class="top-title">智汇文枢</text>
    </view>

    <view class="content">
      <text class="section-title">智能文档处理</text>

      <view class="card-list">
        <view class="feature-card" @tap="goPage('/pages/doc-chat/index')">
          <view class="card-icon">📄</view>
          <view class="card-body">
            <text class="card-title">文档智能操作交互</text>
            <text class="card-desc">支持与文档内容进行智能问答、理解与交互处理</text>
          </view>
        </view>

        <view class="feature-card" @tap="goPage('/pages/extract/index')">
          <view class="card-icon">🧠</view>
          <view class="card-body">
            <text class="card-title">非结构化文档信息提取</text>
            <text class="card-desc">自动提取合同、报告、表单等文档中的关键信息</text>
          </view>
        </view>

        <view class="feature-card" @tap="goPage('/pages/form-fill/index')">
          <view class="card-icon">📊</view>
          <view class="card-body">
            <text class="card-title">表格自定义数据填写</text>
            <text class="card-desc">按规则批量填写表格内容，支持灵活字段映射</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
const goPage = (url) => {
  uni.navigateTo({
    url
  })
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f6f8;
  box-sizing: border-box;
}

.header {
  padding-top: 28rpx;
  padding-bottom: 18rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f6f8;
}

.top-title {
  font-size: 36rpx;
  font-weight: 700;
  color: #111111;
}

.content {
  padding: 24rpx 24rpx 140rpx;
  box-sizing: border-box;
}

.section-title {
  display: block;
  font-size: 44rpx;
  font-weight: 800;
  color: #111111;
  margin-bottom: 28rpx;
}

.card-list {
  display: flex;
  flex-direction: column;
}

.feature-card {
  background: #ffffff;
  border-radius: 24rpx;
  min-height: 220rpx;
  padding: 28rpx 28rpx;
  box-sizing: border-box;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  margin-bottom: 24rpx;
}

.card-icon {
  font-size: 52rpx;
  margin-bottom: 18rpx;
}

.card-body {
  display: flex;
  flex-direction: column;
}

.card-title {
  font-size: 36rpx;
  line-height: 1.4;
  font-weight: 800;
  color: #111111;
  margin-bottom: 10rpx;
}

.card-desc {
  font-size: 26rpx;
  line-height: 1.7;
  color: #666666;
}
</style>