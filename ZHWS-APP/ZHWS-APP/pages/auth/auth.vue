<template>
  <view class="auth-page">
    <view class="auth-wrapper">
      <view class="auth-card">
        <view class="mode-tabs">
          <view
            class="mode-item"
            :class="{ active: isLoginMode }"
            @tap="switchMode(true)"
          >
            登录
          </view>
          <view
            class="mode-item"
            :class="{ active: !isLoginMode }"
            @tap="switchMode(false)"
          >
            注册
          </view>
        </view>

        <view v-if="isLoginMode" class="form-box">
          <text class="form-title">Welcome back</text>
          <text class="form-subtitle">登录后继续使用智能文档处理服务</text>

          <view class="form-group">
            <input
              v-model.trim="loginForm.email"
              class="form-input"
              type="text"
              placeholder="请输入邮箱"
              placeholder-class="input-placeholder"
            />
          </view>

          <view class="form-group">
            <input
              v-model.trim="loginForm.password"
              class="form-input"
              type="password"
              password
              placeholder="请输入密码"
              placeholder-class="input-placeholder"
            />
          </view>

          <view
            class="primary-btn"
            :class="{ disabled: loading }"
            @tap="handleLogin"
          >
            <text>{{ loading ? '登录中...' : '登录' }}</text>
          </view>
        </view>

        <view v-else class="form-box">
          <text class="form-title">Create account</text>
          <text class="form-subtitle">注册后即可体验平台全部功能</text>

          <view class="form-group">
            <input
              v-model.trim="registerForm.username"
              class="form-input"
              type="text"
              placeholder="请输入用户名"
              placeholder-class="input-placeholder"
            />
          </view>

          <view class="form-group">
            <input
              v-model.trim="registerForm.email"
              class="form-input"
              type="text"
              placeholder="请输入邮箱"
              placeholder-class="input-placeholder"
            />
          </view>

          <view class="form-group">
            <input
              v-model.trim="registerForm.password"
              class="form-input"
              type="password"
              password
              placeholder="请输入密码"
              placeholder-class="input-placeholder"
            />
          </view>

          <view
            class="primary-btn"
            :class="{ disabled: loading }"
            @tap="handleRegister"
          >
            <text>{{ loading ? '注册中...' : '注册' }}</text>
          </view>
        </view>

        <view class="bottom-switch">
          <text class="bottom-text">
            {{ isLoginMode ? '还没有账号？' : '已有账号？' }}
          </text>
          <text class="bottom-link" @tap="switchMode(!isLoginMode)">
            {{ isLoginMode ? '去注册' : '去登录' }}
          </text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { reactive, ref } from 'vue'

const isLoginMode = ref(true)
const loading = ref(false)

const loginForm = reactive({
  email: '',
  password: ''
})

const registerForm = reactive({
  username: '',
  email: '',
  password: ''
})

const switchMode = (mode) => {
  isLoginMode.value = mode
}

const showToast = (title) => {
  uni.showToast({
    title,
    icon: 'none'
  })
}

const handleLogin = () => {
  if (loading.value) return

  if (!loginForm.email) {
    showToast('请输入邮箱')
    return
  }

  if (!loginForm.password) {
    showToast('请输入密码')
    return
  }

  loading.value = true

  setTimeout(() => {
    loading.value = false
    showToast('登录成功')

    uni.switchTab({
      url: '/pages/profile/index'
    })
  }, 1000)
}

const handleRegister = () => {
  if (loading.value) return

  if (!registerForm.username) {
    showToast('请输入用户名')
    return
  }

  if (!registerForm.email) {
    showToast('请输入邮箱')
    return
  }

  if (!registerForm.password) {
    showToast('请输入密码')
    return
  }

  loading.value = true

  setTimeout(() => {
    loading.value = false
    showToast('注册成功')
    isLoginMode.value = true

    loginForm.email = registerForm.email
    loginForm.password = ''

    registerForm.username = ''
    registerForm.email = ''
    registerForm.password = ''
  }, 1000)
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f5f5f5 0%, #ececec 100%);
  padding: 60rpx 32rpx;
  box-sizing: border-box;
}

.auth-wrapper {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 120rpx);
  justify-content: center;
}

.auth-card {
  background: #ffffff;
  border-radius: 32rpx;
  padding: 40rpx 32rpx 36rpx;
  box-shadow: 0 16rpx 40rpx rgba(0, 0, 0, 0.08);
}

.mode-tabs {
  height: 88rpx;
  background: #f3f3f3;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  padding: 8rpx;
  margin-bottom: 40rpx;
}

.mode-item {
  flex: 1;
  height: 72rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30rpx;
  color: #7d7d7d;
  font-weight: 600;
}

.mode-item.active {
  background: #d5b076;
  color: #ffffff;
  box-shadow: 0 8rpx 20rpx rgba(213, 176, 118, 0.25);
}

.form-box {
  padding: 12rpx 4rpx 0;
}

.form-title {
  display: block;
  font-size: 52rpx;
  line-height: 1.2;
  color: #1f1f1f;
  font-weight: 800;
  margin-bottom: 14rpx;
}

.form-subtitle {
  display: block;
  font-size: 26rpx;
  line-height: 1.8;
  color: #9a9a9a;
  margin-bottom: 40rpx;
}

.form-group {
  margin-bottom: 24rpx;
}

.form-input {
  width: 100%;
  height: 96rpx;
  border-radius: 20rpx;
  background: #f8f8f8;
  padding: 0 28rpx;
  box-sizing: border-box;
  font-size: 30rpx;
  color: #333333;
  border: 2rpx solid transparent;
}

.input-placeholder {
  color: #c2c2c2;
  font-size: 30rpx;
}

.primary-btn {
  margin-top: 18rpx;
  width: 100%;
  height: 96rpx;
  border-radius: 999rpx;
  background: #d5b076;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 12rpx 24rpx rgba(213, 176, 118, 0.25);
}

.primary-btn text {
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 700;
}

.primary-btn.disabled {
  opacity: 0.72;
}

.bottom-switch {
  margin-top: 36rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12rpx;
}

.bottom-text {
  font-size: 26rpx;
  color: #8a8a8a;
}

.bottom-link {
  font-size: 26rpx;
  color: #d5b076;
  font-weight: 700;
}
</style>