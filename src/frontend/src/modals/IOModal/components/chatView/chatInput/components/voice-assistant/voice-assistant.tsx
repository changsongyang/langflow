import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH, SAVE_API_KEY_ALERT } from "@/constants/constants";
import { useGetMessagesMutation } from "@/controllers/API/queries/messages/use-get-messages-mutation";
import {
  useGetGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useMessagesStore } from "@/stores/messagesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";
import { AxiosError } from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import IconComponent from "../../../../../../../components/common/genericIconComponent";
import AudioSettingsDialog from "./components/audio-settings/audio-settings-dialog";
import { checkProvider } from "./helpers/check-provider";
import { formatTime } from "./helpers/format-time";
import { workletCode } from "./helpers/streamProcessor";
import { useBarControls } from "./hooks/use-bar-controls";
import { useHandleWebsocketMessage } from "./hooks/use-handle-websocket-message";
import { useInitializeAudio } from "./hooks/use-initialize-audio";
import { useInterruptPlayback } from "./hooks/use-interrupt-playback";
import { usePlayNextAudioChunk } from "./hooks/use-play-next-audio-chunk";
import { useStartConversation } from "./hooks/use-start-conversation";
import { useStartRecording } from "./hooks/use-start-recording";
import { useStopRecording } from "./hooks/use-stop-recording";

interface VoiceAssistantProps {
  flowId: string;
  setShowAudioInput: (value: boolean) => void;
}

export function VoiceAssistant({
  flowId,
  setShowAudioInput,
}: VoiceAssistantProps) {
  const [recordingTime, setRecordingTime] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState("");
  const [message, setMessage] = useState("");
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [addKey, setAddKey] = useState(false);
  const [barHeights, setBarHeights] = useState<number[]>(Array(30).fill(20));
  const [preferredLanguage, setPreferredLanguage] = useState(
    localStorage.getItem("lf_preferred_language") || "en-US",
  );

  const waveformRef = useRef<HTMLDivElement>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const processorRef = useRef<AudioWorkletNode | null>(null);
  const audioQueueRef = useRef<AudioBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const microphoneRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  const messagesStore = useMessagesStore();
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const edges = useFlowStore((state) => state.edges);
  const setEdges = useFlowStore((state) => state.setEdges);
  const updateBuildStatus = useFlowStore((state) => state.updateBuildStatus);
  const addDataToFlowPool = useFlowStore((state) => state.addDataToFlowPool);
  const updateEdgesRunningByNodes = useFlowStore(
    (state) => state.updateEdgesRunningByNodes,
  );
  const revertBuiltStatusFromBuilding = useFlowStore(
    (state) => state.revertBuiltStatusFromBuilding,
  );
  const clearEdgesRunningByNodes = useFlowStore(
    (state) => state.clearEdgesRunningByNodes,
  );
  const variables = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );
  const createVariable = usePostGlobalVariables();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const currentSessionId = useUtilityStore((state) => state.currentSessionId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { data: globalVariables } = useGetGlobalVariables();

  const hasOpenAIAPIKey = useMemo(() => {
    return (
      variables?.find((variable) => variable === "OPENAI_API_KEY")?.length! > 0
    );
  }, [variables, open, addKey]);

  const hasElevenLabsApiKey = useMemo(() => {
    return (
      variables?.find((variable) => variable === "ELEVENLABS_API_KEY")
        ?.length! > 0
    );
  }, [variables, addKey, open]);

  const openaiApiKey = useMemo(() => {
    return variables?.find((variable) => variable === "OPENAI_API_KEY");
  }, [variables, addKey]);

  const elevenLabsApiKeyGlobalVariable = useMemo(() => {
    return variables?.find((variable) => variable === "ELEVENLABS_API_KEY");
  }, [variables, addKey]);

  const hasElevenLabsApiKeyEnv = useMemo(() => {
    return Boolean(process.env?.ELEVENLABS_API_KEY);
  }, [variables, addKey]);

  const getMessagesMutation = useGetMessagesMutation();

  const initializeAudio = async () => {
    useInitializeAudio(audioContextRef, setStatus, startConversation);
  };

  const startRecording = async () => {
    useStartRecording(
      audioContextRef,
      microphoneRef,
      analyserRef,
      wsRef,
      setIsRecording,
      playNextAudioChunk,
      isPlayingRef,
      audioQueueRef,
      workletCode,
      processorRef,
      setStatus,
      handleGetMessagesMutation,
    );
  };

  const stopRecording = () => {
    useStopRecording(
      microphoneRef,
      processorRef,
      analyserRef,
      wsRef,
      setIsRecording,
    );
  };

  const playNextAudioChunk = () => {
    usePlayNextAudioChunk(audioQueueRef, isPlayingRef, processorRef);
  };

  const handleWebSocketMessage = (event: MessageEvent) => {
    useHandleWebsocketMessage(
      event,
      interruptPlayback,
      audioContextRef,
      audioQueueRef,
      isPlayingRef,
      playNextAudioChunk,
      setIsBuilding,
      revertBuiltStatusFromBuilding,
      clearEdgesRunningByNodes,
      setMessage,
      edges,
      setStatus,
      messagesStore,
      setEdges,
      addDataToFlowPool,
      updateEdgesRunningByNodes,
      updateBuildStatus,
      hasOpenAIAPIKey,
      showErrorAlert,
    );
  };

  const startConversation = () => {
    useStartConversation(
      flowId,
      wsRef,
      setStatus,
      startRecording,
      handleWebSocketMessage,
      stopRecording,
      currentSessionId,
    );
  };

  const interruptPlayback = () => {
    useInterruptPlayback(audioQueueRef, isPlayingRef, processorRef);
  };

  useBarControls(
    isRecording,
    setRecordingTime,
    barHeights,
    setBarHeights,
    recordingTime,
  );

  const handleGetMessagesMutation = () => {
    getMessagesMutation.mutate({
      mode: "union",
      id: currentSessionId,
    });
  };

  useEffect(() => {
    if (!isRecording && hasOpenAIAPIKey) {
      initializeAudio();
    } else {
      stopRecording();
    }
  }, [hasOpenAIAPIKey]);

  const showErrorAlert = (title: string, list: string[]) => {
    setErrorData({
      title,
      list,
    });
    setIsRecording(false);
  };

  const handleSaveApiKey = async (apiKey: string, variableName: string) => {
    try {
      await createVariable.mutateAsync({
        name: variableName,
        value: apiKey,
        type: "secret",
        default_fields: ["voice_mode"],
      });
      setSuccessData({
        title: SAVE_API_KEY_ALERT,
      });
      setAddKey(!addKey);
    } catch (error) {
      console.error("Error saving API key:", error);
      if (error instanceof AxiosError) {
        setErrorData({
          title: "Error saving API key",
          list: [error.response?.data?.detail ?? "Error saving API key"],
        });
      }
    }
  };

  useEffect(() => {
    checkProvider();

    return () => {
      stopRecording();
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
    };
  }, []);

  const handleCloseAudioInput = () => {
    stopRecording();
    setShowAudioInput(false);
  };

  const handleSetShowSettingsModal = async (
    open: boolean,
    openaiApiKey: string,
    elevenLabsApiKey: string,
  ) => {
    setShowSettingsModal(open);

    if (!open) {
      setRecordingTime(0);
      setBarHeights(Array(30).fill(20));
    }

    if (
      hasElevenLabsApiKey &&
      elevenLabsApiKey &&
      elevenLabsApiKey !== "ELEVENLABS_API_KEY"
    ) {
      setErrorData({
        title: "There's already an API key saved",
        list: ["Please select your ELEVENLABS_API_KEY"],
      });
      return;
    }

    if (hasOpenAIAPIKey && openaiApiKey && openaiApiKey !== "OPENAI_API_KEY") {
      setErrorData({
        title: "There's already an API key saved",
        list: ["Please select your OPENAI_API_KEY"],
      });
      return;
    }

    if (openaiApiKey && openaiApiKey !== "OPENAI_API_KEY") {
      await handleSaveApiKey(openaiApiKey, "OPENAI_API_KEY");
    }

    if (elevenLabsApiKey && elevenLabsApiKey !== "ELEVENLABS_API_KEY") {
      await handleSaveApiKey(elevenLabsApiKey, "ELEVENLABS_API_KEY");
    }

    if (!open && hasOpenAIAPIKey) {
      startConversation();
    }
  };

  const handleToggleRecording = () => {
    if (isRecording) {
      microphoneRef.current?.disconnect();
      setBarHeights(Array(30).fill(20));
      setIsRecording(false);
    } else {
      startRecording();
      setIsRecording(true);
    }
  };

  useEffect(() => {
    if (preferredLanguage) {
      localStorage.setItem("lf_preferred_language", preferredLanguage);
    }
  }, [preferredLanguage]);

  return (
    <>
      <div
        data-testid="voice-assistant-container"
        className="mx-auto flex w-full max-w-[324px] items-center justify-center rounded-md border bg-background px-4 py-2 shadow-xl"
      >
        <div
          className={cn(
            "flex items-center",
            hasOpenAIAPIKey ? "gap-3" : "gap-2",
          )}
        >
          <Button unstyled onClick={handleToggleRecording}>
            <IconComponent
              name={isRecording ? "Mic" : "MicOff"}
              strokeWidth={ICON_STROKE_WIDTH}
              className="h-4 w-4 text-placeholder-foreground"
            />
          </Button>

          <div
            ref={waveformRef}
            className="flex h-5 flex-1 items-center justify-center"
          >
            {barHeights.map((height, index) => (
              <div
                key={index}
                className={cn(
                  "mx-[1px] w-[2px] rounded-sm transition-all duration-200",
                  isRecording && height > 20
                    ? "bg-red-foreground"
                    : "bg-placeholder-foreground",
                )}
                style={{ height: `${height}%` }}
              />
            ))}
          </div>
          <div className="min-w-[50px] cursor-default text-center font-mono text-sm font-medium text-placeholder-foreground">
            {hasOpenAIAPIKey ? formatTime(recordingTime) : "--:--s"}
          </div>

          <div>
            <AudioSettingsDialog
              open={showSettingsModal}
              userOpenaiApiKey={openaiApiKey}
              userElevenLabsApiKey={elevenLabsApiKeyGlobalVariable}
              hasElevenLabsApiKeyEnv={hasElevenLabsApiKeyEnv}
              setShowSettingsModal={handleSetShowSettingsModal}
              hasOpenAIAPIKey={hasOpenAIAPIKey}
              language={preferredLanguage}
              setLanguage={setPreferredLanguage}
            >
              {hasOpenAIAPIKey ? (
                <>
                  <Button
                    data-testid="voice-assistant-settings-icon"
                    onClick={() => setShowSettingsModal(true)}
                    unstyled
                  >
                    <IconComponent
                      name="Settings"
                      strokeWidth={ICON_STROKE_WIDTH}
                      className={cn(
                        "relative top-[2px] h-4 w-4 text-muted-foreground hover:text-foreground",
                      )}
                    />
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    variant={"outlineAmber"}
                    size={"icon"}
                    onClick={() => setShowSettingsModal(true)}
                    data-testid="voice-assistant-settings-icon"
                    className="group h-8 w-8"
                  >
                    <IconComponent
                      name="Settings"
                      strokeWidth={ICON_STROKE_WIDTH}
                      className={cn(
                        "h-4 w-4 text-accent-amber-foreground group-hover:text-accent-amber",
                      )}
                    />
                  </Button>
                </>
              )}
            </AudioSettingsDialog>
          </div>

          <Button
            unstyled
            onClick={handleCloseAudioInput}
            data-testid="voice-assistant-close-button"
          >
            <IconComponent
              name="X"
              strokeWidth={ICON_STROKE_WIDTH}
              className="h-4 w-4 text-muted-foreground hover:text-foreground"
            />
          </Button>
        </div>
      </div>
    </>
  );
}
