<template>
  <view class="page">
    <view class="header-card">
      <text class="title">文档智能操作交互</text>
      <text class="desc">上传文档后，通过自然语言输入处理需求</text>
    </view>

    <view class="card">
      <text class="label">当前文件</text>
      <view class="file-box">
        <text class="file-name">{{ fileName || '未选择文件' }}</text>
        <view class="btn small-btn" @tap="chooseFile">
          <text class="btn-text">选择文件</text>
        </view>
      </view>
    </view>

    <view class="card">
      <text class="label">处理需求</text>
      <textarea
        v-model="commandText"
        class="textarea"
        placeholder="例如：提取摘要、优化排版、调整标题格式"
      />
    </view>

    <view class="btn-row">
      <view class="btn btn-gray" @tap="resetForm">
        <text class="btn-text">重置</text>
      </view>
      <view class="btn" @tap="handleSubmit">
        <text class="btn-text">{{ loading ? '处理中...' : '开始处理' }}</text>
      </view>
    </view>

    <view class="card result-card">
      <text class="label">处理结果</text>

      <view v-if="loading" class="result-empty">
        <text class="result-text">正在处理，请稍候...</text>
      </view>

      <view v-else-if="resultText" class="result-box">
        <text class="result-text">{{ resultText }}</text>
      </view>

      <view v-else class="result-empty">
        <text class="result-text">完成上传并处理后，这里会显示结果</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'

const fileName = ref('')
const commandText = ref('')
const loading = ref(false)
const resultText = ref('')

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
  commandText.value = ''
  resultText.value = ''
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

  if (!commandText.value.trim()) {
    uni.showToast({
      title: '请输入处理需求',
      icon: 'none'
    })
    return
  }

  loading.value = true
  resultText.value = ''

  setTimeout(() => {
    loading.value = false
    resultText.value = `已根据指令完成处理：${commandText.value}`
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
.textarea {
  width: 100%;
  min-height: 220rpx;
  background: #f8f8f8;
  border-radius: 16rpx;
  padding: 20rpx;
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
.result-card {
  min-height: 260rpx;
}
.result-box,
.result-empty {
  background: #f8f8f8;
  border-radius: 16rpx;
  padding: 24rpx;
  min-height: 160rpx;
}
.result-text {
  font-size: 28rpx;
  color: #555555;
  line-height: 1.8;
}
</style>