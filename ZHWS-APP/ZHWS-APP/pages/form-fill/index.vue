<template>
  <view class="page">
    <view class="header-card">
      <text class="title">表格自定义数据填写</text>
      <text class="desc">选择模板和源文档，自动写入表格内容</text>
    </view>

    <view class="card">
      <text class="label">模板文件</text>
      <view class="file-box">
        <text class="file-name">{{ templateFileName || '未选择模板文件' }}</text>
        <view class="btn small-btn" @tap="chooseTemplateFile">
          <text class="btn-text">选模板</text>
        </view>
      </view>
    </view>

    <view class="card">
      <text class="label">源文档</text>
      <view class="file-box">
        <text class="file-name">{{ sourceFileName || '未选择源文档' }}</text>
        <view class="btn small-btn" @tap="chooseSourceFile">
          <text class="btn-text">选文件</text>
        </view>
      </view>
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
        <text class="result-text">正在生成表格结果...</text>
      </view>

      <view v-else-if="resultText" class="result-box">
        <text class="result-text">{{ resultText }}</text>
      </view>

      <view v-else class="result-empty">
        <text class="result-text">处理完成后，这里显示结果说明</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'

const templateFileName = ref('')
const sourceFileName = ref('')
const loading = ref(false)
const resultText = ref('')

const chooseTemplateFile = () => {
  uni.chooseMessageFile({
    count: 1,
    type: 'file',
    success: (res) => {
      const file = res.tempFiles?.[0]
      templateFileName.value = file?.name || '已选择模板'
    },
    fail: () => {
      uni.showToast({
        title: '选择模板失败',
        icon: 'none'
      })
    }
  })
}

const chooseSourceFile = () => {
  uni.chooseMessageFile({
    count: 1,
    type: 'file',
    success: (res) => {
      const file = res.tempFiles?.[0]
      sourceFileName.value = file?.name || '已选择文件'
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
  templateFileName.value = ''
  sourceFileName.value = ''
  resultText.value = ''
  loading.value = false
}

const handleSubmit = () => {
  if (!templateFileName.value) {
    uni.showToast({
      title: '请先选择模板文件',
      icon: 'none'
    })
    return
  }

  if (!sourceFileName.value) {
    uni.showToast({
      title: '请先选择源文档',
      icon: 'none'
    })
    return
  }

  loading.value = true
  resultText.value = ''

  setTimeout(() => {
    loading.value = false
    resultText.value = '已完成表格自动填写，可继续接入下载结果文件逻辑'
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