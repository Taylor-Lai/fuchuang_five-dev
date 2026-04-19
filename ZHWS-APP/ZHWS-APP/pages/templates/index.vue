<template>
  <view class="page">
    <!-- 顶部简介 -->
    <view class="hero-card">
      <text class="hero-badge">模板库</text>
      <text class="hero-title">支持预览与使用</text>
      <text class="hero-desc">
        提供合同、人事、财务、项目等多场景模板，支持搜索、分类筛选、收藏和使用。
      </text>

      <view class="hero-btn-row">
        <view class="action-btn primary-btn" @tap="resetFilter">
          <text class="btn-text">查看全部模板</text>
        </view>
        <view class="action-btn secondary-btn" @tap="goEditor">
          <text class="secondary-text">在线编辑</text>
        </view>
      </view>
    </view>

    <!-- 搜索 -->
    <view class="card">
      <input
        v-model.trim="keyword"
        class="search-input"
        placeholder="搜索模板名称、分类、场景"
      />
    </view>

    <!-- 分类 -->
    <view class="card">
      <text class="section-title">模板分类</text>
      <scroll-view scroll-x class="category-scroll">
        <view class="category-row">
          <view
            class="category-btn"
            :class="{ active: activeCategory === '全部' }"
            @tap="activeCategory = '全部'"
          >
            <text>全部</text>
          </view>

          <view
            v-for="item in categories"
            :key="item"
            class="category-btn"
            :class="{ active: activeCategory === item }"
            @tap="activeCategory = item"
          >
            <text>{{ item }}</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 模板列表 -->
    <view class="list-card">
      <view class="list-head">
        <text class="section-title">模板列表</text>
        <text class="list-count">共 {{ filteredTemplates.length }} 个</text>
      </view>

      <view
        v-for="item in filteredTemplates"
        :key="item.id"
        class="template-item"
      >
        <view class="template-top">
          <view class="template-main">
            <text class="template-name">{{ item.name }}</text>
            <text class="template-scene">{{ item.scene }}</text>
          </view>

          <view
            class="fav-btn"
            :class="{ active: item.isFavorite }"
            @tap="toggleFavorite(item)"
          >
            <text>{{ item.isFavorite ? '★' : '☆' }}</text>
          </view>
        </view>

        <view class="tag-row">
          <text class="template-tag">{{ item.category }}</text>
          <text v-if="item.isHot" class="hot-tag">热门</text>
        </view>

        <text class="template-desc">{{ item.description }}</text>

        <view class="template-meta">
          <text>字段：{{ item.fields }}</text>
          <text>格式：{{ item.format }}</text>
        </view>

        <view class="template-actions">
          <view class="mini-btn preview-btn" @tap="previewTemplate(item)">
            <text class="mini-btn-text">预览</text>
          </view>

          <view class="mini-btn secondary-mini-btn" @tap="useTemplate(item)">
            <text class="secondary-mini-text">使用</text>
          </view>
        </view>
      </view>

      <view v-if="!filteredTemplates.length" class="empty-box">
        <text>没有找到符合条件的模板</text>
      </view>
    </view>

    <!-- 预览弹窗 -->
    <view v-if="previewVisible" class="mask" @tap="closePreview">
      <view class="preview-dialog" @tap.stop>
        <view class="preview-head">
          <view class="preview-title-box">
            <text class="preview-title">{{ currentTemplate?.name }}</text>
            <text class="preview-subtitle">
              {{ currentTemplate?.category }}｜{{ currentTemplate?.scene }}
            </text>
          </view>

          <text class="close-btn" @tap="closePreview">×</text>
        </view>

        <view class="preview-block">
          <text class="preview-label">模板说明</text>
          <text class="preview-text">{{ currentTemplate?.description }}</text>
        </view>

        <view class="preview-block">
          <text class="preview-label">字段列表</text>
          <view class="field-list">
            <text
              v-for="field in currentTemplate?.fieldList || []"
              :key="field"
              class="field-item"
            >
              {{ field }}
            </text>
          </view>
        </view>

        <view class="preview-actions">
          <view class="action-btn secondary-btn small-action" @tap="closePreview">
            <text class="secondary-text">关闭</text>
          </view>
          <view class="action-btn primary-btn small-action" @tap="useTemplate(currentTemplate)">
            <text class="btn-text">使用模板</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'

const keyword = ref('')
const activeCategory = ref('全部')
const previewVisible = ref(false)
const currentTemplate = ref(null)

const templateList = ref([
  {
    id: 1,
    name: '合同信息登记表',
    category: '行政办公',
    scene: '合同管理',
    description: '适用于合同基础信息登记、审批流转及归档管理。',
    fields: 12,
    format: 'Excel / 在线表单',
    isHot: true,
    isFavorite: false,
    fieldList: ['合同编号', '合同名称', '甲方', '乙方', '签订日期', '金额']
  },
  {
    id: 2,
    name: '员工入职信息表',
    category: '人事管理',
    scene: '员工档案',
    description: '用于员工入职基础信息采集，支持岗位和联系方式录入。',
    fields: 15,
    format: 'Excel / 在线表单',
    isHot: true,
    isFavorite: false,
    fieldList: ['姓名', '性别', '身份证号', '手机号', '部门', '岗位']
  },
  {
    id: 3,
    name: '费用报销申请表',
    category: '财务管理',
    scene: '费用报销',
    description: '适合日常差旅、办公采购、项目支出等报销场景。',
    fields: 10,
    format: 'Excel / 在线表单',
    isHot: true,
    isFavorite: false,
    fieldList: ['申请人', '部门', '报销事由', '费用类型', '金额', '审批人']
  },
  {
    id: 4,
    name: '项目进度跟踪表',
    category: '项目管理',
    scene: '进度管理',
    description: '适合团队项目阶段任务跟踪、负责人分配与完成状态记录。',
    fields: 13,
    format: 'Excel / 在线表单',
    isHot: false,
    isFavorite: false,
    fieldList: ['项目名称', '阶段名称', '任务名称', '负责人', '截止时间', '状态']
  },
  {
    id: 5,
    name: '病历信息采集表',
    category: '医疗场景',
    scene: '病历整理',
    description: '用于从病历文档中提取患者基本信息和诊断结果。',
    fields: 14,
    format: 'Excel / 在线表单',
    isHot: true,
    isFavorite: false,
    fieldList: ['姓名', '性别', '年龄', '住院号', '科室', '诊断结果']
  }
])

const categories = computed(() => {
  return [...new Set(templateList.value.map(item => item.category))]
})

const filteredTemplates = computed(() => {
  const key = keyword.value.toLowerCase()

  return templateList.value.filter(item => {
    const matchCategory =
      activeCategory.value === '全部' || item.category === activeCategory.value

    const matchKeyword =
      !key ||
      item.name.toLowerCase().includes(key) ||
      item.category.toLowerCase().includes(key) ||
      item.scene.toLowerCase().includes(key)

    return matchCategory && matchKeyword
  })
})

const previewTemplate = (item) => {
  currentTemplate.value = item
  previewVisible.value = true
}

const closePreview = () => {
  previewVisible.value = false
}

const toggleFavorite = (item) => {
  item.isFavorite = !item.isFavorite

  uni.showToast({
    title: item.isFavorite ? '已收藏' : '已取消收藏',
    icon: 'none'
  })
}

const useTemplate = (item) => {
  if (!item) return

  uni.showToast({
    title: `使用模板：${item.name}`,
    icon: 'none'
  })

  setTimeout(() => {
    uni.navigateTo({
      url: '/pages/form-fill/index'
    })
  }, 300)
}

const goEditor = () => {
  uni.switchTab({
    url: '/pages/editor/index'
  })
}

const resetFilter = () => {
  keyword.value = ''
  activeCategory.value = '全部'
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
.card,
.list-card {
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

.hero-btn-row {
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

.small-action {
  flex: none;
  min-width: 180rpx;
  padding: 0 24rpx;
}

.primary-btn {
  background: #d5b076;
}

.secondary-btn {
  background: #ffffff;
  border: 2rpx solid #e8d6b4;
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

.search-input {
  width: 100%;
  height: 84rpx;
  background: #f8f8f8;
  border-radius: 16rpx;
  padding: 0 20rpx;
  box-sizing: border-box;
  font-size: 28rpx;
}

.section-title {
  display: block;
  font-size: 30rpx;
  font-weight: 800;
  color: #222222;
  margin-bottom: 18rpx;
}

.category-scroll {
  white-space: nowrap;
}

.category-row {
  display: flex;
  gap: 16rpx;
}

.category-btn {
  padding: 0 24rpx;
  height: 68rpx;
  border-radius: 34rpx;
  background: #f6f6f6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666666;
  font-size: 26rpx;
  flex-shrink: 0;
}

.category-btn.active {
  background: #d5b076;
  color: #ffffff;
}

.list-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.list-count {
  font-size: 24rpx;
  color: #999999;
}

.template-item {
  background: #f9f9f9;
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
}

.template-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16rpx;
}

.template-main {
  flex: 1;
}

.template-name {
  display: block;
  font-size: 32rpx;
  font-weight: 800;
  color: #222222;
}

.template-scene {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #b48742;
}

.fav-btn {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34rpx;
  color: #bbbbbb;
}

.fav-btn.active {
  color: #f4b400;
}

.tag-row {
  display: flex;
  gap: 12rpx;
  margin-top: 16rpx;
}

.template-tag,
.hot-tag {
  display: inline-flex;
  align-items: center;
  height: 44rpx;
  padding: 0 16rpx;
  border-radius: 22rpx;
  font-size: 22rpx;
}

.template-tag {
  background: rgba(213, 176, 118, 0.14);
  color: #b48742;
}

.hot-tag {
  background: rgba(216, 79, 79, 0.12);
  color: #d84f4f;
}

.template-desc {
  display: block;
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #666666;
  line-height: 1.8;
}

.template-meta {
  margin-top: 16rpx;
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
  font-size: 24rpx;
  color: #999999;
}

.template-actions {
  display: flex;
  gap: 16rpx;
  margin-top: 20rpx;
}

.mini-btn {
  flex: 1;
  height: 72rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-btn {
  background: #ffffff;
  border: 2rpx solid #e8d6b4;
}

.secondary-mini-btn {
  background: #d5b076;
}

.mini-btn-text {
  color: #b48742;
  font-size: 26rpx;
  font-weight: 700;
}

.secondary-mini-text {
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 700;
}

.empty-box {
  background: #f8f8f8;
  border-radius: 20rpx;
  padding: 40rpx 20rpx;
  text-align: center;
  color: #999999;
  font-size: 26rpx;
}

.mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.preview-dialog {
  width: 100%;
  background: #ffffff;
  border-top-left-radius: 28rpx;
  border-top-right-radius: 28rpx;
  padding: 28rpx 24rpx 40rpx;
  box-sizing: border-box;
  max-height: 80vh;
}

.preview-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.preview-title-box {
  flex: 1;
}

.preview-title {
  display: block;
  font-size: 34rpx;
  font-weight: 800;
  color: #222222;
}

.preview-subtitle {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #999999;
}

.close-btn {
  font-size: 42rpx;
  color: #999999;
  line-height: 1;
}

.preview-block {
  background: #f8f8f8;
  border-radius: 18rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
}

.preview-label {
  display: block;
  font-size: 26rpx;
  font-weight: 700;
  color: #222222;
  margin-bottom: 12rpx;
}

.preview-text {
  font-size: 26rpx;
  color: #666666;
  line-height: 1.8;
}

.field-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.field-item {
  padding: 10rpx 18rpx;
  border-radius: 999rpx;
  background: #ffffff;
  color: #b48742;
  font-size: 24rpx;
}

.preview-actions {
  display: flex;
  gap: 20rpx;
  justify-content: flex-end;
}
</style>