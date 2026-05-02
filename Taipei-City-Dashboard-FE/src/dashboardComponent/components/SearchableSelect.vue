<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from "vue";

const props = defineProps({
	modelValue: { type: [String, Number], default: "" },
	options: { type: Array, default: () => [] },
	placeholder: { type: String, default: "請選擇" },
	disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

const isOpen = ref(false);
const search = ref("");
const selectorRef = ref(null);
const dropdownRef = ref(null);
const dropdownStyle = ref({});

const filteredOptions = computed(() => {
	if (!search.value) return props.options;
	return props.options.filter((opt) =>
		opt.label.toLowerCase().includes(search.value.toLowerCase()),
	);
});

const displayValue = computed(() => {
	const selected = props.options.find((o) => o.value === props.modelValue);
	return selected ? selected.label : props.placeholder;
});

function updatePosition() {
	if (!selectorRef.value || !isOpen.value) return;
	const rect = selectorRef.value.getBoundingClientRect();
	const spaceBelow = window.innerHeight - rect.bottom - 8;
	const spaceAbove = rect.top - 8;
	const openUp = spaceBelow < 200 && spaceAbove > spaceBelow;
	const maxHeight = Math.min(
		280,
		Math.max(160, Math.max(spaceBelow, spaceAbove)),
	);

	dropdownStyle.value = {
		position: "fixed",
		left: `${rect.left}px`,
		width: `${rect.width}px`,
		zIndex: 99999,
		maxHeight: `${maxHeight}px`,
	};

	if (openUp) {
		dropdownStyle.value.top = `${Math.max(8, rect.top - maxHeight - 4)}px`;
	} else {
		dropdownStyle.value.top = `${rect.bottom + 4}px`;
	}
}

function toggleDropdown() {
	if (props.disabled) return;
	isOpen.value = !isOpen.value;
	if (isOpen.value) {
		search.value = "";
		nextTick(() => {
			updatePosition();
		});
	}
}

function selectOption(opt) {
	emit("update:modelValue", opt.value);
	isOpen.value = false;
}

function closeDropdown(e) {
	if (
		selectorRef.value?.contains(e.target) ||
		dropdownRef.value?.contains(e.target)
	) {
		return;
	}
	isOpen.value = false;
}

onMounted(() => {
	document.addEventListener("click", closeDropdown);
	window.addEventListener("resize", updatePosition);
	window.addEventListener("scroll", updatePosition, true);
});

onUnmounted(() => {
	document.removeEventListener("click", closeDropdown);
	window.removeEventListener("resize", updatePosition);
	window.removeEventListener("scroll", updatePosition, true);
});
</script>

<template>
	<div class="searchable-select" :class="{ disabled }" ref="selectorRef">
		<div class="ss-display" @click="toggleDropdown">
			<span class="ss-value" :class="{ 'is-placeholder': !modelValue }">{{
				displayValue
			}}</span>
			<span class="material-icons ss-arrow">{{
				isOpen ? "expand_less" : "expand_more"
			}}</span>
		</div>

		<Teleport to="body">
			<div
				v-if="isOpen"
				ref="dropdownRef"
				class="ss-dropdown"
				:style="dropdownStyle"
			>
				<input
					v-model="search"
					class="ss-search"
					placeholder="搜尋..."
					@click.stop
				/>
				<div class="ss-list">
					<div
						v-for="opt in filteredOptions"
						:key="opt.value"
						class="ss-item"
						:class="{ active: opt.value === modelValue }"
						@click="selectOption(opt)"
					>
						{{ opt.label }}
					</div>
					<div v-if="!filteredOptions.length" class="ss-empty">
						無符合項目
					</div>
				</div>
			</div>
		</Teleport>
	</div>
</template>

<style scoped>
.searchable-select {
	position: relative;
	width: 100%;
}
.searchable-select.disabled {
	opacity: 0.5;
	pointer-events: none;
}
.ss-display {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 8px 12px;
	background: var(--color-component-background, rgba(30, 42, 56, 0.8));
	border: 1px solid var(--color-border, #47596e);
	border-radius: 6px;
	cursor: pointer;
	min-height: 36px;
}
.ss-display:hover {
	border-color: #2979ff;
}
.ss-value {
	font-size: 13px;
	color: #e5edf7;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.ss-value.is-placeholder {
	color: #8a9bb0;
}
.ss-arrow {
	font-size: 18px;
	color: #8a9bb0;
}
</style>

<style>
/* Teleported styles */
.ss-dropdown {
	position: fixed;
	background: #1e2a38;
	border: 1px solid #47596e;
	border-radius: 6px;
	box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
	display: flex;
	flex-direction: column;
	overflow: hidden;
}
.ss-search {
	padding: 8px 12px;
	background: transparent;
	border: none;
	border-bottom: 1px solid #2d3e50;
	color: #e5edf7;
	font-size: 13px;
	outline: none;
}
.ss-search::placeholder {
	color: #8a9bb0;
}
.ss-list {
	flex: 1;
	overflow-y: auto;
	min-height: 0;
	padding-bottom: 8px;
}
.ss-item {
	padding: 8px 12px;
	font-size: 13px;
	color: #cfd8e3;
	cursor: pointer;
}
.ss-item:hover {
	background: rgba(41, 121, 255, 0.12);
}
.ss-item.active {
	color: #2979ff;
	font-weight: bold;
}
.ss-empty {
	padding: 12px;
	text-align: center;
	color: #8a9bb0;
	font-size: 13px;
}
</style>
