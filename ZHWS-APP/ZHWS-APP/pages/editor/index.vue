<template>
  <view class="page">
    <!-- 顶部介绍 -->
    <view class="hero-card">
      <text class="hero-badge">在线编辑</text>
      <text class="hero-title">自定义模板并保存到模板库</text>
      <text class="hero-desc">
        你可以编辑模板名称、分类、场景、字段、标签等信息，并保存到本地模板库。
      </text>

      <view class="hero-actions">
        <view class="action-btn secondary-btn" @tap="goTemplateLibrary">
          <text class="secondary-text">返回模板库</text>
        </view>
        <view class="action-btn primary-btn" @tap="saveTemplate" :class="{ disabled: saving }">
          <text class="btn-text">{{ saving ? '保存中...' : '保存模板' }}</text>
        </view>
      </view>
    </view>

    <!-- 基础信息 -->
    <view class="card">
      <text class="section-title">模板基础信息</text>

      <view class="form-item">
        <text class="label">模板名称</text>
        <input v-model.trim="templateForm.name" class="input" placeholder="例如：项目验收登记表" />
      </view>

      <view class="form-item">
        <text class="label">模板分类</text>
        <input v-model.trim="templateForm.category" class="input" placeholder="例如：项目管理 / 行政办公" />
      </view>

      <view class="form-item">
        <text class="label">适用场景</text>
        <input v-model.trim="templateForm.scene" class="input" placeholder="例如：项目验收 / 入职登记" />
      </view>

      <view class="form-item">
        <text class="label">输出格式</text>
        <input v-model.trim="templateForm.format" class="input" placeholder="例如：Excel / 在线表单" />
      </view>

      <view class="form-item">
        <text class="label">模板描述</text>
        <textarea
          v-model.trim="templateForm.description"
          class="textarea"
          placeholder="请输入模板说明"
        />
      </view>

      <view class="form-item">
        <text class="label">模板标签（逗号分隔）</text>
        <input v-model.trim="tagsInput" class="input" placeholder="例如：项目, 验收, 登记" />
      </view>
    </view>

    <!-- 字段配置 -->
    <view class="card">
      <view class="section-head">
        <text class="section-title">字段配置</text>
        <view class="mini-action-btn" @tap="addField">
          <text class="mini-action-text">新增字段</text>
        </view>
      </view>

      <view v-if="templateForm.fields.length">
        <view
          v-for="(field, index) in templateForm.fields"
          :key="field.id"
          class="field-card"
        >
          <view class="field-top">
            <text class="field-index">字段 {{ index + 1 }}</text>
            <text class="delete-text" @tap="removeField(index)">删除</text>
          </view>

          <view class="form-item">
            <text class="label">字段名称</text>
            <input
              v-model.trim="field.label"
              class="input"
              placeholder="例如：姓名 / 合同编号"
            />
          </view>

          <view class="form-item">
            <text class="label">字段标识</text>
            <input
              v-model.trim="field.key"
              class="input"
              placeholder="例如：name / contractNo"
            />
          </view>

          <view class="form-item">
            <text class="label">字段类型</text>
            <picker :range="fieldTypeOptions" @change="onTypeChange($event, index)">
              <view class="picker-box">
                <text>{{ getFieldTypeText(field.type) }}</text>
              </view>
            </picker>
          </view>

          <view class="switch-row" @tap="field.required = !field.required">
            <text class="label">是否必填</text>
            <view class="required-badge" :class="{ active: field.required }">
              <text>{{ field.required ? '是' : '否' }}</text>
            </view>
          </view>
        </view>
      </view>

      <view v-else class="empty-box">
        <text>暂无字段，请点击“新增字段”</text>
      </view>

      <view class="bottom-actions">
        <view class="action-btn gray-btn" @tap="resetTemplate">
          <text class="btn-text">重置模板</text>
        </view>
      </view>
    </view>

    <!-- 模板预览 -->
    <view class="card">
      <text class="section-title">模板预览</text>

      <view class="preview-panel">
        <text class="preview-title">{{ previewData.name || '未命名模板' }}</text>

        <view class="preview-meta">
          <text class="meta-tag">{{ previewData.category || '自定义分类' }}</text>
          <text class="meta-tag">{{ previewData.scene || '在线编辑' }}</text>
          <text class="meta-tag">{{ previewData.format || 'Excel / 在线表单' }}</text>
          <text class="meta-tag">{{ previewData.fields.length }} 个字段</text>
        </view>

        <text class="preview-desc">
          {{ previewData.description || '暂无模板描述' }}
        </text>

        <view class="preview-block">
          <text class="preview-label">模板标签</text>
          <view class="tag-list">
            <text
              v-for="tag in previewData.tags"
              :key="tag"
              class="tag-item"
            >
              {{ tag }}
            </text>
          </view>
        </view>

        <view class="preview-block">
          <text class="preview-label">字段列表</text>
          <view class="tag-list">
            <text
              v-for="field in previewData.fields"
              :key="field.id"
              class="field-tag"
            >
              {{ field.label || field.key || '未命名字段' }}
            </text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'

const TEMPLATE_LIBRARY_STORAGE_KEY = 'local_template_library_v1'

const saving = ref(false)

const fieldTypeOptions = ['text', 'number', 'date', 'textarea', 'select']

const createField = () => ({
  id: `field_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
  label: '',
  key: '',
  type: 'text',
  required: false
})

const createDefaultTemplate = () => ({
  id: `tpl_${Date.now()}`,
  name: '',
  category: '自定义分类',
  scene: '在线编辑',
  description: '',
  format: 'Excel / 在线表单',
  fields: [createField(), createField()]
})

const templateForm = ref(createDefaultTemplate())
const tagsInput = ref('本地上传, 自定义模板')

const parsedTags = computed(() => {
  return tagsInput.value
    .split(/[,，]/)
    .map(item => item.trim())
    .filter(Boolean)
})

const previewData = computed(() => {
  return {
    ...templateForm.value,
    tags: parsedTags.value
  }
})

const addField = () => {
  templateForm.value.fields.push(createField())
}

const removeField = (index) => {
  templateForm.value.fields.splice(index, 1)
}

const resetTemplate = () => {
  templateForm.value = createDefaultTemplate()
  tagsInput.value = '本地上传, 自定义模板'
}

const getFieldTypeText = (type) => {
  const map = {
    text: '文本',
    number: '数字',
    date: '日期',
    textarea: '多行文本',
    select: '下拉选项'
  }
  return map[type] || '文本'
}

const onTypeChange = (e, index) => {
  const selectedIndex = Number(e.detail.value)
  templateForm.value.fields[index].type = fieldTypeOptions[selectedIndex]
}

const validateForm = () => {
  if (!templateForm.value.name.trim()) {
    uni.showToast({
      title: '请填写模板名称',
      icon: 'none'
    })
    return false
  }

  if (!templateForm.value.fields.length) {
    uni.showToast({
      title: '请至少添加一个字段',
      icon: 'none'
    })
    return false
  }

  const invalidField = templateForm.value.fields.find(
    field => !String(field.label || '').trim() && !String(field.key || '').trim()
  )

  if (invalidField) {
    uni.showToast({
      title: '每个字段至少填写名称或标识',
      icon: 'none'
    })
    return false
  }

  return true
}

const buildUploadPayload = () => {
  return {
    id: templateForm.value.id,
    name: templateForm.value.name || '未命名模板',
    category: templateForm.value.category || '自定义分类',
    scene: templateForm.value.scene || '在线编辑',
    description:
      templateForm.value.description ||
      `本地上传模板：${templateForm.value.name || '未命名模板'}`,
    format: templateForm.value.format || 'Excel / 在线表单',
    tags: parsedTags.value.length ? parsedTags.value : ['本地上传'],
    likes: 0,
    comments: 0,
    isHot: false,
    source: 'local',
    createdAt: Date.now(),
    fields: templateForm.value.fields.map((field, index) => ({
      id: field.id || `field_${index + 1}`,
      label: field.label || `字段${index + 1}`,
      key: field.key || `field_${index + 1}`,
      type: field.type || 'text',
      required: Boolean(field.required)
    }))
  }
}

const saveTemplate = () => {
  if (saving.value) return
  if (!validateForm()) return

  try {
    saving.value = true

    const payload = buildUploadPayload()
    const raw = uni.getStorageSync(TEMPLATE_LIBRARY_STORAGE_KEY)

    let libraryList = []
    if (raw) {
      try {
        libraryList = JSON.parse(raw)
        if (!Array.isArray(libraryList)) libraryList = []
      } catch (e) {
        libraryList = []
      }
    }

    const existedIndex = libraryList.findIndex(item => item.id === payload.id)

    if (existedIndex > -1) {
      libraryList.splice(existedIndex, 1, payload)
    } else {
      libraryList.unshift(payload)
    }

    uni.setStorageSync(TEMPLATE_LIBRARY_STORAGE_KEY, JSON.stringify(libraryList))

    uni.showToast({
      title: '保存成功',
      icon: 'none'
    })

    setTimeout(() => {
      uni.switchTab({
        url: '/pages/templates/index'
      })
    }, 400)
  } catch (error) {
    uni.showToast({
      title: '保存失败',
      icon: 'none'
    })
  } finally {
    saving.value = false
  }
}

const goTemplateLibrary = () => {
  uni.switchTab({
    url: '/pages/templates/index'
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

.hero-card,
.card {
  background: #ffffff;
  border-radius: 24rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 120rpx;
  height: 44rpx;
  border-radius: 22rpx;
  background: rgba(213, 176, 118, 0.16);
  color: #b48742;
  font-size: 22rpx;
  margin-bottom: 18rpx;
}

.hero-title {
  display: block;
  font-size: 42rpx;
  font-weight: 800;
  color: #111111;
  line-height: 1.4;
}

.hero-desc {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  line-height: 1.8;
  color: #666666;
}

.hero-actions {
  margin-top: 24rpx;
  display: flex;
  gap: 20rpx;
}

.action-btn {
  flex: 1;
  height: 84rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.primary-btn {
  background: #d5b076;
}

.secondary-btn {
  background: #ffffff;
  border: 2rpx solid #e8d6b4;
}

.gray-btn {
  background: #9a9a9a;
}

.disabled {
  opacity: 0.7;
}

.btn-text {
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 700;
}

.secondary-text {
  color: #b48742;
  font-size: 28rpx;
  font-weight: 700;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
}

.section-title {
  display: block;
  font-size: 30rpx;
  font-weight: 800;
  color: #222222;
  margin-bottom: 18rpx;
}

.mini-action-btn {
  min-width: 150rpx;
  height: 64rpx;
  border-radius: 32rpx;
  padding: 0 20rpx;
  background: #faf6ef;
  border: 2rpx solid #ead8ba;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mini-action-text {
  color: #b48742;
  font-size: 24rpx;
  font-weight: 700;
}

.form-item {
  margin-bottom: 22rpx;
}

.label {
  display: block;
  font-size: 26rpx;
  color: #666666;
  margin-bottom: 10rpx;
}

.input,
.textarea,
.picker-box {
  width: 100%;
  background: #f8f8f8;
  border-radius: 16rpx;
  padding: 0 20rpx;
  box-sizing: border-box;
  font-size: 28rpx;
  color: #333333;
}

.input,
.picker-box {
  height: 84rpx;
  display: flex;
  align-items: center;
}

.textarea {
  min-height: 180rpx;
  padding: 20rpx;
}

.field-card {
  background: #f9f9f9;
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
}

.field-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.field-index {
  font-size: 28rpx;
  font-weight: 700;
  color: #222222;
}

.delete-text {
  font-size: 24rpx;
  color: #d84f4f;
}

.switch-row {
  height: 84rpx;
  background: #f8f8f8;
  border-radius: 16rpx;
  padding: 0 20rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.required-badge {
  min-width: 72rpx;
  height: 44rpx;
  border-radius: 22rpx;
  padding: 0 16rpx;
  background: #e5e5e5;
  color: #666666;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
}

.required-badge.active {
  background: #d5b076;
  color: #ffffff;
}

.empty-box {
  background: #f8f8f8;
  border-radius: 20rpx;
  padding: 40rpx 20rpx;
  text-align: center;
  color: #999999;
  font-size: 26rpx;
}

.bottom-actions {
  margin-top: 10rpx;
}

.preview-panel {
  background: #f8f8f8;
  border-radius: 20rpx;
  padding: 20rpx;
}

.preview-title {
  display: block;
  font-size: 34rpx;
  font-weight: 800;
  color: #222222;
}

.preview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-top: 16rpx;
}

.meta-tag {
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: #ffffff;
  color: #b48742;
  font-size: 22rpx;
}

.preview-desc {
  display: block;
  margin-top: 18rpx;
  font-size: 26rpx;
  line-height: 1.8;
  color: #666666;
}

.preview-block {
  margin-top: 20rpx;
}

.preview-label {
  display: block;
  font-size: 26rpx;
  font-weight: 700;
  color: #222222;
  margin-bottom: 12rpx;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.tag-item,
.field-tag {
  padding: 10rpx 18rpx;
  border-radius: 999rpx;
  font-size: 24rpx;
}

.tag-item {
  background: #ffffff;
  color: #777777;
}

.field-tag {
  background: #faf6ef;
  color: #b48742;
}
</style>