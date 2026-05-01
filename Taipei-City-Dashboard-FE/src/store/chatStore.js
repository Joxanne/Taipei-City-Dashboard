import { ref } from "vue";
import { defineStore } from "pinia";
import http from "../router/axios";
import { useAuthStore } from "./authStore";

export const useChatStore = defineStore("chat", () => {
	const authStore = useAuthStore();

	const isOpen = ref(false);
	const view = ref("sessions");
	const sessionList = ref([]);
	const currentSessionId = ref(null);
	const isLoading = ref(false);
	const defaultChatData = [
		{
			id: 1,
			role: "bot",
			isDefault: true,
			content:
				"您好，我是【臺北城市儀表板】小幫手，很高興為您服務！\n 您可以： \n\n • 點擊左側既有的儀表板主題，快速查看各主題內容 \n • 輸入您感興趣的主題描述，我會自動為您組建最適合的儀表板 \n\n 如果有想了解的內容，歡迎直接告訴我，我會盡力協助！\n\n 📩 聯絡信箱：tuic@gov.taipei \n 🏢 臺北大數據中心 \n\n",
		},
	];
	const chatData = ref([...defaultChatData]);

	const openPanel = () => {
		isOpen.value = true;
		if (sessionList.value.length === 0) {
			fetchSessions();
		}
	};

	const closePanel = () => {
		isOpen.value = false;
	};

	const togglePanel = () => {
		if (isOpen.value) {
			closePanel();
		} else {
			openPanel();
		}
	};

	const generateSessionId = () => {
		const d = new Date();
		const ts =
			d.getFullYear() +
			String(d.getMonth() + 1).padStart(2, "0") +
			String(d.getDate()).padStart(2, "0") +
			String(d.getHours()).padStart(2, "0") +
			String(d.getMinutes()).padStart(2, "0") +
			String(d.getSeconds()).padStart(2, "0");

		return "session_" + ts;
	};

	const decodeAnswer = (answer) => {
		if (!answer || typeof document === "undefined") return answer || "";

		const textarea = document.createElement("textarea");
		textarea.innerHTML = answer;
		return textarea.value;
	};

	const getReadableAnswer = (answer) => {
		const decodedAnswer = decodeAnswer(answer);

		try {
			const parsed = JSON.parse(decodedAnswer);
			if (Array.isArray(parsed)) {
				return "已為您找到相關組件。";
			}
			if (typeof parsed === "string") {
				return parsed;
			}
			return decodedAnswer;
		} catch {
			return decodedAnswer;
		}
	};

	const fetchSessions = async () => {
		if (!authStore.token) {
			sessionList.value = [];
			return;
		}

		try {
			const response = await http.get("/chatlog/session");
			sessionList.value = response.data?.data || [];
		} catch (error) {
			console.error("fetchSessions error:", error);
		}
	};

	const handleNewSession = () => {
		currentSessionId.value = generateSessionId();
		chatData.value = [...defaultChatData];
		view.value = "chat";
	};

	const openSession = async (sessionId) => {
		if (!authStore.token) {
			chatData.value = [...defaultChatData];
			view.value = "chat";
			addChatData({
				role: "bot",
				content: "請先登入會員以使用此功能喔！",
			});
			return;
		}

		currentSessionId.value = sessionId;
		chatData.value = [...defaultChatData];
		view.value = "chat";

		try {
			const response = await http.get(`/chatlog/session/${sessionId}`);
			const logs = response.data?.data || [];
			logs.forEach((log) => {
				chatData.value.push({
					id: chatData.value.length + 1,
					role: "user",
					isDefault: false,
					content: log.question,
				});
				chatData.value.push({
					id: chatData.value.length + 1,
					role: "bot",
					isDefault: false,
					content: getReadableAnswer(log.answer),
				});
			});
		} catch (error) {
			console.error("openSession error:", error);
		}
	};

	const deleteSession = async (sessionId) => {
		if (!authStore.token) return;

		try {
			await http.delete(`/chatlog/session/${sessionId}`);
			if (currentSessionId.value === sessionId) {
				currentSessionId.value = null;
				chatData.value = [...defaultChatData];
				view.value = "sessions";
			}
			await fetchSessions();
		} catch (error) {
			console.error("deleteSession error:", error);
		}
	};

	const handleBackToSessions = async () => {
		currentSessionId.value = null;
		chatData.value = [...defaultChatData];
		view.value = "sessions";
		await fetchSessions();
	};

	const addChatData = (newChatData) => {
		chatData.value.push({
			id: chatData.value.length + 1,
			isDefault: false,
			...newChatData,
		});
	};

	const buildMessages = () => {
		return chatData.value
			.filter((m) => !m.isDefault && (m.role === "user" || m.role === "bot"))
			.map((m) => ({
				role: m.role === "bot" ? "assistant" : "user",
				content: m.content,
			}));
	};

	const addQueryData = async (newChatData) => {
		if (!currentSessionId.value) {
			currentSessionId.value = generateSessionId();
		}

		addChatData(newChatData);

		if (!authStore.token) {
			addChatData({
				role: "bot",
				content: "請先登入會員以使用此功能喔！",
			});
			return;
		}

		isLoading.value = true;

		try {
			const response = await http.post("/ai/chat/twai", {
				session: currentSessionId.value,
				messages: buildMessages(),
			});
			const aiData = response.data?.data;
			const aiContent = aiData?.content || "很抱歉，目前無法產生回覆，請稍後再試。";

			chatData.value.push({
				id: chatData.value.length + 1,
				role: "bot",
				isDefault: false,
				content: aiContent,
			});

			await saveChatLog(newChatData.content, aiContent);
		} catch (error) {
			console.error("AiChatError :", error);
			const status = error.response?.status;
			const content =
				status === 401 || status === 403
					? "請先登入會員以使用此功能喔！"
					: "很抱歉，目前無法完成查詢，請稍後再試。";

			chatData.value.push({
				id: chatData.value.length + 1,
				role: "bot",
				isDefault: false,
				content,
			});
		} finally {
			isLoading.value = false;
		}
	};

	const saveChatLog = async (question, answer) => {
		if (!currentSessionId.value || !authStore.token) return;

		try {
			const formData = new FormData();
			formData.append("session", currentSessionId.value);
			formData.append("question", question);
			formData.append("answer", answer);

			await http.post("/chatlog/", formData, {
				headers: {
					"Content-Type": "multipart/form-data",
				},
			});
		} catch (error) {
			console.error("saveChatLog error:", error);
		}
	};

	return {
		isOpen,
		view,
		sessionList,
		currentSessionId,
		chatData,
		isLoading,
		openPanel,
		closePanel,
		togglePanel,
		fetchSessions,
		handleNewSession,
		openSession,
		deleteSession,
		handleBackToSessions,
		addChatData,
		addQueryData,
	};
});
