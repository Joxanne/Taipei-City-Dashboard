<script setup>
import { ref, computed } from "vue";
import { useMapStore } from "../../store/mapStore";
import { useChatStore } from "../../store/chatStore";

const mapStore = useMapStore();
const chatStore = useChatStore();

const selectedLayerId = ref(null);
const filteredFeatures = ref([]);
const isFiltering = ref(false);
const hasResult = ref(false);
const showAIInput = ref(false);
const userQuestion = ref("");

const visibleLayers = computed(() =>
	mapStore.currentVisibleLayers
		.filter(
			(id) =>
				!id.startsWith("isochrone-") && !id.startsWith("filtered-"),
		)
		.map((id) => ({
			id,
			title: mapStore.mapConfigs[id]?.title || id,
		})),
);

function onLayerChange() {
	hasResult.value = false;
	mapStore.clearFilteredLayer();
}

function runFilter() {
	if (!selectedLayerId.value) return;
	isFiltering.value = true;
	try {
		const features = mapStore.filterPOIsInIsochrone(selectedLayerId.value);
		filteredFeatures.value = features;
		mapStore.addFilteredLayer(features);
		hasResult.value = true;
	} finally {
		isFiltering.value = false;
	}
}

function clearResult() {
	filteredFeatures.value = [];
	hasResult.value = false;
	showAIInput.value = false;
	userQuestion.value = "";
	mapStore.clearFilteredLayer();
}

function openAIInput() {
	showAIInput.value = true;
}

async function confirmSendToAI() {
	const title =
		mapStore.mapConfigs[selectedLayerId.value]?.title || "站點";
	await chatStore.sendFilterResultsToAI(
		filteredFeatures.value,
		title,
		userQuestion.value,
	);
	showAIInput.value = false;
	userQuestion.value = "";
}
</script>

<template>
  <div class="filterpanel">
    <p class="filterpanel-title">
      等時圈範圍過濾
    </p>

    <div
      v-if="!mapStore.isochroneState.visible"
      class="filterpanel-hint"
    >
      請先計算通勤圈
    </div>

    <template v-else>
      <div class="filterpanel-section">
        <label>選擇圖層</label>
        <p
          v-if="visibleLayers.length === 0"
          class="filterpanel-empty"
        >
          尚無可見圖層
        </p>
        <div
          v-else
          class="filterpanel-layers"
        >
          <label
            v-for="layer in visibleLayers"
            :key="layer.id"
            class="filterpanel-radio"
          >
            <input
              v-model="selectedLayerId"
              type="radio"
              :value="layer.id"
              @change="onLayerChange"
            >
            {{ layer.title }}
          </label>
        </div>
      </div>

      <div class="filterpanel-actions">
        <button
          class="filterpanel-actions-clear"
          :disabled="!hasResult"
          @click="clearResult"
        >
          清除
        </button>
        <button
          class="filterpanel-actions-run"
          :disabled="!selectedLayerId || isFiltering"
          @click="runFilter"
        >
          {{ isFiltering ? "過濾中..." : "開始過濾" }}
        </button>
      </div>

      <div
        v-if="hasResult"
        class="filterpanel-result"
      >
        <p class="filterpanel-result-count">
          找到 <strong>{{ filteredFeatures.length }}</strong> 個符合站點
        </p>

        <template v-if="!showAIInput">
          <button
            class="filterpanel-result-ai"
            @click="openAIInput"
          >
            送 AI 分析
          </button>
        </template>

        <template v-else>
          <textarea
            v-model="userQuestion"
            class="filterpanel-result-input"
            placeholder="輸入追加問題，如：哪些站點到站時間較短？"
            rows="3"
          />
          <div class="filterpanel-result-btns">
            <button
              class="filterpanel-result-cancel"
              @click="showAIInput = false; userQuestion = ''"
            >
              取消
            </button>
            <button
              class="filterpanel-result-confirm"
              @click="confirmSendToAI"
            >
              確認送出
            </button>
          </div>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.filterpanel {
	position: absolute;
	right: 52px;
	top: 150px;
	width: 210px;
	padding: 12px;
	border: 1px solid var(--color-border);
	border-radius: 8px;
	background-color: var(--color-component-background);
	z-index: 2;
	box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);

	&-title {
		font-size: var(--font-s);
		color: var(--color-complement-text);
		margin-bottom: 8px;
		font-weight: 600;
		letter-spacing: 0.05em;
	}

	&-hint {
		font-size: var(--font-s);
		color: var(--color-complement-text);
		opacity: 0.5;
	}

	&-empty {
		font-size: var(--font-s);
		color: var(--color-complement-text);
		opacity: 0.5;
	}

	&-section {
		display: flex;
		flex-direction: column;
		margin-bottom: 10px;

		label {
			font-size: var(--font-s);
			color: var(--color-complement-text);
			margin-bottom: 6px;
		}
	}

	&-layers {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	&-radio {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: var(--font-s);
		color: var(--color-normal-text);
		cursor: pointer;

		input[type="radio"] {
			accent-color: var(--color-highlight);
			cursor: pointer;
		}
	}

	&-actions {
		display: flex;
		justify-content: flex-end;
		gap: 6px;
		margin-bottom: 8px;

		button {
			padding: 4px 10px;
			border-radius: 5px;
			font-size: var(--font-s);
			cursor: pointer;
			transition: opacity 0.2s;

			&:hover {
				opacity: 0.8;
			}

			&:disabled {
				opacity: 0.4;
				cursor: not-allowed;
			}
		}

		&-clear {
			background: transparent;
			border: 1px solid var(--color-border);
			color: var(--color-complement-text);
		}

		&-run {
			background-color: var(--color-highlight);
			border: none;
			color: white;
		}
	}

	&-result {
		border-top: 1px solid var(--color-border);
		padding-top: 8px;
		display: flex;
		flex-direction: column;
		gap: 6px;

		&-count {
			font-size: var(--font-s);
			color: var(--color-complement-text);

			strong {
				color: var(--color-highlight);
			}
		}

		&-ai {
			width: 100%;
			padding: 5px 0;
			border-radius: 5px;
			background-color: var(--color-component-background);
			border: 1px solid var(--color-highlight);
			color: var(--color-highlight);
			font-size: var(--font-s);
			cursor: pointer;
			transition: background-color 0.2s, color 0.2s;

			&:hover {
				background-color: var(--color-highlight);
				color: white;
			}
		}

		&-input {
			width: 100%;
			padding: 6px 8px;
			border-radius: 5px;
			border: 1px solid var(--color-border);
			background-color: var(--color-component-background);
			color: var(--color-normal-text);
			font-size: var(--font-s);
			resize: none;
			box-sizing: border-box;

			&::placeholder {
				color: var(--color-complement-text);
				opacity: 0.5;
			}

			&:focus {
				outline: none;
				border-color: var(--color-highlight);
			}
		}

		&-btns {
			display: flex;
			gap: 6px;
			margin-top: 6px;

			button {
				flex: 1;
				padding: 4px 0;
				border-radius: 5px;
				font-size: var(--font-s);
				cursor: pointer;
				transition: opacity 0.2s;

				&:hover {
					opacity: 0.8;
				}
			}
		}

		&-cancel {
			background: transparent;
			border: 1px solid var(--color-border);
			color: var(--color-complement-text);
		}

		&-confirm {
			background-color: var(--color-highlight);
			border: none;
			color: white;
		}
	}
}

</style>
