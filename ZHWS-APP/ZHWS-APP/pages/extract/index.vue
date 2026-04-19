<template>
  <view class="page">
    <view class="header-card">
      <text class="title">非结构化文档信息提取</text>
      <text class="desc">上传文件并填写提取字段，自动识别关键信息</text>
    </view>

    <view class="card">
      <text class="label">选择文件</text>
      <view class="file-box">
        <text class="file-name">{{ fileName || '未选择文件' }}</text>
        <view class="btn small-btn" @tap="chooseFile">
          <text class="btn-text">选择文件</text>
        </view>
      </view>
    </view>

    <view class="card">
      <text class="label">提取字段</text>
      <input
        v-model="fieldsText"
        class="input"
        placeholder="例如：姓名, 身份证号, 电话"
      />
    </view>

    <view class="btn-row">
      <view class="btn btn-gray" @tap="resetForm">
        <text class="btn-text">重置</text>
      </view>
      <view class="btn" @tap="handleSubmit">
        <text class="btn-text">{{ loading ? '处理中...' : '开始提取' }}</text>
      </view>
    </view>

    <view class="card">
      <text class="label">提取结果</text>

      <view v-if="loading" class="result-empty">
        <text class="result-text">正在识别字段内容...</text>
      </view>

      <view v-else-if="resultList.length" class="result-list">
        <view
          v-for="(item, index) in resultList"
          :key="index"
          class="result-item"
        >
          <text class="result-key">{{ item.label }}</text>
          <text class="result-value">{{ item.value }}</text>
        </view>
      </view>

      <view v-else class="result-empty">
        <text class="result-text">提取完成后，这里展示字段结果</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'

const fileName = ref('')
const fieldsText = ref('')
const loading = ref(false)
const resultList = ref([])

const chooseFile = () => {
  uni.chooseMessageFile({
    count: 1,
    type: 'file',
    success: (res) => {
      const file = res.tempFiles?.[0]
      fileName.value = file?.name || '已选择文件'
    },
    fail: () => {
      uni.showToast({
        title: '选择文件失败',
        icon: 'none'
      })
    }
  })
}

const resetForm = () => {
  fileName.value = ''
  fieldsText.value = ''
  resultList.value = []
  loading.value = false
}

const handleSubmit = () => {
  if (!fileName.value) {
    uni.showToast({
      title: '请先选择文件',
      icon: 'none'
    })
    return
  }

  if (!fieldsText.value.trim()) {
    uni.showToast({
      title: '请输入提取字段',
      icon: 'none'
    })
    return
  }

  loading.value = true
  resultList.value = []

  setTimeout(() => {
    const fields = fieldsText.value
      .split(',')
      .map(item => item.trim())
      .filter(Boolean)

    resultList.value = fields.map(field => ({
      label: field,
      value: '示例识别内容'
    }))

    loading.value = false
  }, 1500)
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f6f8;
  padding: 24rpx;
  box-sizing: border-box;
}
.header-card,
.card {
  background: #ffffff;
  border-radius: 24rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
}
.title {
  display: block;
  font-size: 40rpx;
  font-weight: 800;
  color: #111111;
}
.desc {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #777777;
  line-height: 1.7;
}
.label {
  display: block;
  font-size: 28rpx;
  font-weight: 700;
  color: #222222;
  margin-bottom: 18rpx;
}
.file-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}
.file-name {
  flex: 1;
  font-size: 28rpx;
  color: #555555;
  word-break: break-all;
}
.input {
  width: 100%;
  height: 88rpx;
  background: #f8f8f8;
  border-radius: 16rpx;
  padding: 0 20rpx;
  box-sizing: border-box;
  font-size: 28rpx;
}
.btn-row {
  display: flex;
  gap: 20rpx;
  margin-bottom: 24rpx;
}
.btn {
  flex: 1;
  height: 88rpx;
  border-radius: 999rpx;
  background: #d5b076;
  display: flex;
  align-items: center;
  justify-content: center;
}
.small-btn {
  flex: none;
  width: 180rpx;
  height: 68rpx;
  border-radius: 14rpx;
}
.btn-gray {
  background: #9a9a9a;
}
.btn-text {
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 700;
}
.result-empty {
  background: #f8f8f8;
  border-radius: 16rpx;
  padding: 24rpx;
  min-height: 160rpx;
}
.result-text {
  font-size: 28rpx;
  color: #666666;
}
.result-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}
.result-item {
  background: #f8f8f8;
  border-radius: 16rpx;
  padding: 20rpx;
}
.result-key {
  display: block;
  font-size: 26rpx;
  color: #b48742;
  font-weight: 700;
  margin-bottom: 8rpx;
}
.result-value {
  display: block;
  font-size: 28rpx;
  color: #333333;
  line-height: 1.7;
}
</style>