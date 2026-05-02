<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import SendIcon from "../icons/SendIcon.vue";
import BotLogo from "../icons/BotLogo.vue";
import UserLogo from "../icons/UserLogo.vue";

import { CHAT_TOOL_GROUPS, useChatStore } from "../../store/chatStore";

const chatStore = useChatStore();
const {
	isOpen,
	view,
	sessionList,
	chatData,
	isLoading,
	currentSessionId,
	activeToolGroups,
} = storeToRefs(chatStore);
const {
	closePanel,
	handleNewSession,
	openSession,
	deleteSession,
	handleBackToSessions,
	addQueryData,
	toggleToolGroup,
} = chatStore;

const userMessage = ref("");
const chatAreaRef = ref(null);
const isToolMenuOpen = ref(false);
const toolMenuRef = ref(null);
const panelWidth = ref(380);
const isResizing = ref(false);
const isStickyVisible = ref(true);
const bodyCursorBeforeResize = ref("");
const bodyUserSelectBeforeResize = ref("");

const activeToolGroupItems = computed(() =>
	activeToolGroups.value
		.map((id) => CHAT_TOOL_GROUPS.find((group) => group.id === id))
		.filter(Boolean),
);

const formatSessionDate = (session) => {
	if (!session.created_at) return session.session;

	const d = new Date(session.created_at);
	return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
};

const getSessionTitle = (session) => {
	return session.question || session.session;
};

const handleSendMessage = (text) => {
	if (!text.trim() || isLoading.value) return;

	addQueryData({
		role: "user",
		content: text,
	});
	userMessage.value = "";
};

const handleDeleteSession = (sessionId) => {
	if (!window.confirm("確定要刪除此對話嗎？")) return;
	deleteSession(sessionId);
};

const handleCloseSticky = () => {
	isStickyVisible.value = false;
};

const handleToolMenuToggle = () => {
	isToolMenuOpen.value = !isToolMenuOpen.value;
};

const handleToolMenuClickOutside = (event) => {
	if (toolMenuRef.value && !toolMenuRef.value.contains(event.target)) {
		isToolMenuOpen.value = false;
	}
};

const handleResizeMove = (event) => {
	if (!isResizing.value) return;

	const minWidth = 320;
	const maxWidth = Math.min(720, window.innerWidth - 80);
	const nextWidth = window.innerWidth - event.clientX;
	panelWidth.value = Math.min(Math.max(nextWidth, minWidth), maxWidth);
};

const handleResizeEnd = () => {
	if (!isResizing.value) return;

	isResizing.value = false;
	document.removeEventListener("pointermove", handleResizeMove);
	document.removeEventListener("pointerup", handleResizeEnd);
	document.removeEventListener("pointercancel", handleResizeEnd);
	document.body.style.cursor = bodyCursorBeforeResize.value;
	document.body.style.userSelect = bodyUserSelectBeforeResize.value;
};

const handleResizeStart = (event) => {
	if (event.button !== undefined && event.button !== 0) return;

	isResizing.value = true;
	event.preventDefault();
	bodyCursorBeforeResize.value = document.body.style.cursor;
	bodyUserSelectBeforeResize.value = document.body.style.userSelect;
	document.addEventListener("pointermove", handleResizeMove);
	document.addEventListener("pointerup", handleResizeEnd);
	document.addEventListener("pointercancel", handleResizeEnd);
	document.body.style.cursor = "ew-resize";
	document.body.style.userSelect = "none";
};

watch(
	() => chatData.value.length,
	async () => {
		await nextTick();
		const chat = chatAreaRef.value;
		if (!chat) return;
		chat.scrollTop = chat.scrollHeight - chat.clientHeight;
	},
	{ deep: true },
);

onMounted(() => {
	document.addEventListener("click", handleToolMenuClickOutside);
});

onBeforeUnmount(() => {
	document.removeEventListener("click", handleToolMenuClickOutside);
	if (isResizing.value) {
		handleResizeEnd();
	}
});
</script>

<template>
  <Transition name="fade">
    <div
      v-if="isOpen"
      class="chatsidepanel-overlay"
      @click="closePanel"
    />
  </Transition>
  <Transition name="slide">
    <div
      v-if="isOpen"
      class="chatsidepanel"
      :class="{ 'chatsidepanel-resizing': isResizing }"
      :style="{ width: `${panelWidth}px` }"
    >
      <div
        class="chatsidepanel-resizer"
        title="調整寬度"
        @pointerdown="handleResizeStart"
      />
      <div
        v-if="view === 'sessions'"
        class="chatsidepanel-view"
      >
        <div class="chatsidepanel-header">
          <span class="chatsidepanel-header-title">小幫手</span>
          <div class="chatsidepanel-header-actions">
            <button
              class="chatsidepanel-new-btn"
              @click="handleNewSession"
            >
              <span>edit_square</span>
              新對話
            </button>
            <button
              class="chatsidepanel-icon-btn"
              title="關閉"
              @click="closePanel"
            >
              <span>close</span>
            </button>
          </div>
        </div>

        <div class="chatsidepanel-session-list">
          <div
            v-if="sessionList.length === 0"
            class="chatsidepanel-session-empty"
          >
            <p>尚無對話紀錄</p>
            <button
              class="chatsidepanel-empty-btn"
              @click="handleNewSession"
            >
              開始新對話
            </button>
          </div>
          <button
            v-for="session in sessionList"
            :key="session.session"
            class="chatsidepanel-session-item"
            @click="openSession(session.session)"
          >
            <span class="chatsidepanel-session-icon">description</span>
            <span class="chatsidepanel-session-item-content">
              <span class="chatsidepanel-session-item-title">
                {{ getSessionTitle(session) }}
              </span>
              <span class="chatsidepanel-session-item-date">
                {{ formatSessionDate(session) }}
              </span>
            </span>
            <span
              class="chatsidepanel-session-delete"
              title="刪除此對話"
              @click.stop="handleDeleteSession(session.session)"
            >
              delete
            </span>
          </button>
        </div>
      </div>

      <div
        v-else
        class="chatsidepanel-view"
      >
        <div class="chatsidepanel-header">
          <button
            class="chatsidepanel-icon-btn"
            title="返回"
            @click="handleBackToSessions"
          >
            <span>arrow_back</span>
          </button>
          <span class="chatsidepanel-header-title">小幫手</span>
          <div class="chatsidepanel-header-actions">
            <button
              v-if="currentSessionId"
              class="chatsidepanel-icon-btn"
              title="刪除此對話"
              @click="handleDeleteSession(currentSessionId)"
            >
              <span>delete</span>
            </button>
            <button
              class="chatsidepanel-icon-btn"
              title="關閉"
              @click="closePanel"
            >
              <span>close</span>
            </button>
          </div>
        </div>

        <div class="chatsidepanel-disclaimer">
          AI 回覆僅供參考，可能含有錯誤。
        </div>

        <div
          ref="chatAreaRef"
          class="chatsidepanel-body scrollbar-custom"
        >
          <div
            v-if="isStickyVisible"
            class="chatsidepanel-sticky"
          >
            <div class="chatsidepanel-sticky-header">
              <span>置頂公告：小幫手使用須知</span>
              <button
                class="chatsidepanel-sticky-close"
                title="關閉公告"
                @click="handleCloseSticky"
              >
                <span>close</span>
              </button>
            </div>
            <div class="chatsidepanel-sticky-body">
              小幫手能回答城市數據、交通、環境、人口等相關問題。AI 回覆僅供參考，如有疑問請以原始資料為準。
            </div>
          </div>

          <div
            v-for="chat in chatData"
            :key="chat.id"
            class="chatsidepanel-message"
          >
            <div
              v-if="chat.role === 'bot'"
              class="chatsidepanel-message-bot"
            >
              <div class="chatsidepanel-avatar">
                <BotLogo />
              </div>
              <div class="chatsidepanel-message-content">
                <div
                  v-if="chat.content"
                  class="chatsidepanel-bubble"
                >
                  <p>{{ chat.content }}</p>
                </div>
              </div>
            </div>

            <div
              v-else
              class="chatsidepanel-message-user"
            >
              <div class="chatsidepanel-avatar">
                <UserLogo />
              </div>
              <div
                v-if="chat.content"
                class="chatsidepanel-message-content"
              >
                <div class="chatsidepanel-bubble">
                  <p>{{ chat.content }}</p>
                </div>
              </div>
            </div>
          </div>

          <div
            v-if="isLoading"
            class="chatsidepanel-loading"
          >
            <div class="chatsidepanel-loading-dot" />
            <div class="chatsidepanel-loading-dot" />
            <div class="chatsidepanel-loading-dot" />
          </div>
        </div>

        <div
          v-if="activeToolGroupItems.length > 0"
          class="chatsidepanel-active-tools"
        >
          <button
            v-for="group in activeToolGroupItems"
            :key="group.id"
            class="chatsidepanel-active-tool-chip"
            :title="`移除 ${group.label}`"
            @click="toggleToolGroup(group.id)"
          >
            <span>{{ group.icon }}</span>
            {{ group.label }}
            <span class="chatsidepanel-active-tool-remove">close</span>
          </button>
        </div>

        <div
          ref="toolMenuRef"
          class="chatsidepanel-tool-area"
        >
          <div
            v-if="isToolMenuOpen"
            class="chatsidepanel-tool-dropdown"
          >
            <button
              v-for="group in CHAT_TOOL_GROUPS"
              :key="group.id"
              class="chatsidepanel-tool-option"
              :class="{
                'chatsidepanel-tool-option--active':
                  activeToolGroups.includes(group.id),
              }"
              @click.stop="toggleToolGroup(group.id)"
            >
              <span class="chatsidepanel-tool-option-icon">
                {{ group.icon }}
              </span>
              <span class="chatsidepanel-tool-option-label">
                {{ group.label }}
              </span>
              <span
                v-if="activeToolGroups.includes(group.id)"
                class="chatsidepanel-tool-option-check"
              >
                check
              </span>
            </button>
          </div>

          <div class="chatsidepanel-input">
            <div class="chatsidepanel-tool-menu">
              <button
                class="chatsidepanel-tool-btn"
                :class="{
                  'chatsidepanel-tool-btn--active': activeToolGroups.length > 0,
                }"
                title="選擇工具"
                @click.stop="handleToolMenuToggle"
              >
                <span>add</span>
              </button>
            </div>
            <input
              v-model="userMessage"
              type="text"
              placeholder="詢問小幫手..."
              :disabled="isLoading"
              @keyup.enter="handleSendMessage(userMessage)"
            >
            <button
              class="chatsidepanel-send-btn"
              :disabled="isLoading || !userMessage.trim()"
              @click="handleSendMessage(userMessage)"
            >
              <SendIcon />
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped lang="scss">
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
	transition: transform 0.25s ease;
}

.slide-enter-from,
.slide-leave-to {
	transform: translateX(100%);
}

.chatsidepanel-overlay {
	position: fixed;
	inset: 0;
	z-index: 99;
	background: transparent;
}

.chatsidepanel {
	width: 380px;
	height: calc(100vh - 60px);
	display: flex;
	flex-direction: column;
	position: fixed;
	top: 60px;
	right: 0;
	z-index: 100;
	border-left: 1px solid var(--color-border);
	background-color: var(--color-component-background);

	&.chatsidepanel-resizing {
		transition: none;
	}

	.chatsidepanel-view {
		height: 100%;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
}

.chatsidepanel-resizer {
	width: 8px;
	height: 100%;
	position: absolute;
	top: 0;
	left: -4px;
	z-index: 2;
	cursor: ew-resize;

	&::after {
		width: 1px;
		height: 100%;
		display: block;
		margin-left: 4px;
		background-color: transparent;
		content: "";
		transition: background-color 0.15s;
	}

	&:hover::after {
		background-color: var(--color-highlight);
	}
}

.chatsidepanel-header {
	min-height: 52px;
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--color-border);
	background-color: var(--color-component-background);

	.chatsidepanel-header-title {
		flex: 1;
		color: var(--color-normal-text);
		font-size: var(--font-m);
		font-weight: 600;
	}

	.chatsidepanel-header-actions {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}
}

.chatsidepanel-icon-btn,
.chatsidepanel-new-btn,
.chatsidepanel-empty-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	border: none;
	border-radius: 4px;
	background: transparent;
	color: var(--color-complement-text);
	transition: background-color 0.15s, color 0.15s, filter 0.15s;
	cursor: pointer;

	span {
		font-family: var(--font-icon);
	}

	&:hover {
		background-color: var(--color-complement-text);
		color: var(--color-normal-text);
	}
}

.chatsidepanel-icon-btn {
	width: 28px;
	height: 28px;

	span {
		font-size: 18px;
	}
}

.chatsidepanel-new-btn,
.chatsidepanel-empty-btn {
	height: 28px;
	gap: 4px;
	padding: 2px 8px;
	border: 1px solid var(--color-border);
	color: var(--color-normal-text);
	font-size: var(--font-s);

	span {
		font-size: 16px;
	}
}

.chatsidepanel-empty-btn {
	background-color: var(--color-highlight);
	color: white;

	&:hover {
		filter: brightness(1.15);
	}
}

.chatsidepanel-disclaimer {
	padding: 0.35rem 1rem;
	border-bottom: 1px solid var(--color-border);
	color: var(--color-complement-text);
	font-size: var(--font-s);
	text-align: center;
}

.chatsidepanel-session-list {
	flex: 1;
	padding: 0.5rem 0;
	overflow-y: auto;

	&::-webkit-scrollbar {
		width: 2px;
	}

	&::-webkit-scrollbar-thumb {
		border-radius: 4px;
		background: var(--color-border);
	}
}

.chatsidepanel-session-empty {
	height: 100%;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 1rem;
	padding: 3rem 1rem;
	color: var(--color-complement-text);

	p {
		margin: 0;
		font-size: var(--font-s);
	}
}

.chatsidepanel-session-item {
	width: 100%;
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.75rem 1rem;
	border: none;
	border-bottom: 1px solid var(--color-border);
	background: transparent;
	text-align: left;
	transition: background-color 0.15s;
	cursor: pointer;

	&:hover {
		background-color: rgba(255, 255, 255, 0.04);

		.chatsidepanel-session-delete {
			opacity: 1;
		}
	}
}

.chatsidepanel-session-icon,
.chatsidepanel-session-delete {
	flex-shrink: 0;
	color: var(--color-complement-text);
	font-family: var(--font-icon);
	font-size: 18px;
}

.chatsidepanel-session-item-content {
	min-width: 0;
	display: flex;
	flex: 1;
	flex-direction: column;
	gap: 2px;
}

.chatsidepanel-session-item-title,
.chatsidepanel-session-item-date {
	display: block;
	font-size: var(--font-s);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.chatsidepanel-session-item-title {
	color: var(--color-normal-text);
}

.chatsidepanel-session-item-date {
	color: var(--color-complement-text);
}

.chatsidepanel-session-delete {
	opacity: 0;
	transition: opacity 0.15s, color 0.15s;

	&:hover {
		color: #ef4444;
	}
}

.chatsidepanel-body {
	flex: 1;
	padding: 0.75rem;
	background-color: var(--color-background);
	overflow-y: auto;

	&::-webkit-scrollbar {
		width: 2px;
		background: transparent;
	}

	&::-webkit-scrollbar-thumb {
		border-radius: 8px;
		background: var(--color-border);
	}
}

.scrollbar-x-hide {
	scrollbar-width: none;

	&::-webkit-scrollbar {
		display: none;
	}
}

.chatsidepanel-sticky {
	padding: 4px 10px;
	position: sticky;
	top: 0;
	z-index: 10;
	margin: 0 8px 0.75rem;
	border: 1px solid var(--color-border);
	border-radius: 6px;
	background-color: var(--color-background);

	.chatsidepanel-sticky-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 6px 10px;
		color: var(--color-normal-text);
		font-size: var(--font-s);
		font-weight: bold;
	}

	.chatsidepanel-sticky-body {
		padding: 6px 10px;
		color: var(--color-complement-text);
		font-size: var(--font-s);
		font-weight: 400;
	}

	.chatsidepanel-sticky-close {
		width: 22px;
		height: 22px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border: none;
		border-radius: 4px;
		background: none;
		color: var(--color-normal-text);
		transition: background-color 0.15s;
		cursor: pointer;

		span {
			font-family: var(--font-icon);
			font-size: 16px;
		}

		&:hover {
			background-color: var(--color-border);
		}
	}
}

.chatsidepanel-message {
	padding: 8px 0;

	.chatsidepanel-message-bot,
	.chatsidepanel-message-user {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
	}

	.chatsidepanel-message-user {
		flex-direction: row-reverse;
	}
}

.chatsidepanel-avatar {
	width: 32px;
	height: 32px;
	display: flex;
	align-items: center;
	justify-content: center;
	flex-shrink: 0;

	svg {
		width: 100%;
		height: auto;
	}
}

.chatsidepanel-message-content {
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.chatsidepanel-bubble {
	max-width: min(100%, 520px);
	border: 1px solid var(--color-border);
	border-radius: 8px;
	background-color: var(--color-component-background);

	p {
		margin: 0;
		padding: 8px 14px;
		color: var(--color-normal-text);
		font-size: var(--font-s);
		line-height: 1.5;
		white-space: pre-line;
		word-break: break-word;
	}
}

.chatsidepanel-loading {
	display: flex;
	gap: 5px;
	padding: 12px 8px;
}

.chatsidepanel-loading-dot {
	width: 7px;
	height: 7px;
	border-radius: 50%;
	background-color: var(--color-complement-text);
	animation: chatdot 1.2s infinite ease-in-out;

	&:nth-child(1) {
		animation-delay: 0s;
	}

	&:nth-child(2) {
		animation-delay: 0.2s;
	}

	&:nth-child(3) {
		animation-delay: 0.4s;
	}
}

@keyframes chatdot {
	0%,
	80%,
	100% {
		opacity: 0.4;
		transform: scale(0.8);
	}

	40% {
		opacity: 1;
		transform: scale(1.2);
	}
}

.chatsidepanel-input {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.75rem 1rem;
	background-color: var(--color-component-background);

	input[type="text"] {
		height: 36px;
		flex: 1;
		padding: 0 1rem;
		border: 1px solid var(--color-border);
		border-radius: 20px;
		outline: none;
		background-color: var(--color-background);
		color: var(--color-normal-text);
		font-size: var(--font-s);
		transition: border-color 0.15s;

		&::placeholder {
			color: var(--color-complement-text);
		}

		&:focus {
			border-color: var(--color-highlight);
		}

		&:disabled {
			opacity: 0.5;
		}
	}

	.chatsidepanel-send-btn {
		width: 36px;
		height: 36px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border: none;
		border-radius: 50%;
		background-color: var(--color-highlight);
		transition: filter 0.15s, opacity 0.15s;
		cursor: pointer;

		&:hover:not(:disabled) {
			filter: brightness(1.2);
		}

		&:disabled {
			opacity: 0.4;
			cursor: not-allowed;
		}
	}
}

.chatsidepanel-active-tools {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	padding: 6px 1rem;
	border-top: 1px solid var(--color-border);
	background-color: var(--color-component-background);
}

.chatsidepanel-active-tool-chip {
	height: 24px;
	display: flex;
	align-items: center;
	gap: 4px;
	padding: 0 8px;
	border: 1px solid var(--color-highlight);
	border-radius: 12px;
	background: transparent;
	color: var(--color-highlight);
	font-size: var(--font-s);
	transition: background-color 0.15s;
	cursor: pointer;

	span {
		font-family: var(--font-icon);
		font-size: 14px;
	}

	&:hover {
		background-color: rgba(90, 156, 248, 0.12);
	}
}

.chatsidepanel-active-tool-remove {
	margin-left: 2px;
}

.chatsidepanel-tool-area {
	border-top: 1px solid var(--color-border);
	background-color: var(--color-component-background);
}

.chatsidepanel-tool-menu {
	flex-shrink: 0;
}

.chatsidepanel-tool-btn {
	width: 36px;
	height: 36px;
	display: flex;
	align-items: center;
	justify-content: center;
	flex-shrink: 0;
	border: 1px solid var(--color-border);
	border-radius: 50%;
	background: transparent;
	color: var(--color-complement-text);
	transition: background-color 0.15s, border-color 0.15s, color 0.15s;
	cursor: pointer;

	span {
		font-family: var(--font-icon);
		font-size: 20px;
	}

	&:hover {
		background-color: rgba(255, 255, 255, 0.06);
		color: var(--color-normal-text);
	}

	&.chatsidepanel-tool-btn--active {
		border-color: var(--color-highlight);
		color: var(--color-highlight);
	}
}

.chatsidepanel-tool-dropdown {
	display: flex;
	flex-direction: column;
	gap: 4px;
	margin: 0.75rem 1rem 0;
	border: 1px solid var(--color-border);
	border-radius: 8px;
	background-color: var(--color-component-background);
	box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.chatsidepanel-tool-option {
	width: 100%;
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 10px 12px;
	border: none;
	background: transparent;
	color: var(--color-normal-text);
	font-size: var(--font-s);
	text-align: left;
	transition: background-color 0.15s;
	cursor: pointer;

	&:hover {
		background-color: rgba(255, 255, 255, 0.06);
	}

	&.chatsidepanel-tool-option--active {
		color: var(--color-highlight);
	}
}

.chatsidepanel-tool-option-icon {
	flex-shrink: 0;
	font-family: var(--font-icon);
	font-size: 18px;
}

.chatsidepanel-tool-option-label {
	flex: 1;
}

.chatsidepanel-tool-option-check {
	flex-shrink: 0;
	color: var(--color-highlight);
	font-family: var(--font-icon);
	font-size: 16px;
}

@media (max-width: 600px) {
	.chatsidepanel,
	.chatsidepanel-overlay {
		display: none;
	}
}
</style>
