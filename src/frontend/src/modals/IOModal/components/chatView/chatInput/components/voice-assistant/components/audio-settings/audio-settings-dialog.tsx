import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { getPlaceholder } from "@/components/core/parameterRenderComponent/helpers/get-placeholder-disabled";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { useGetVoiceList } from "@/controllers/API/queries/voice/use-get-voice-list";
import GeneralDeleteConfirmationModal from "@/shared/components/delete-confirmation-modal";
import GeneralGlobalVariableModal from "@/shared/components/global-variable-modal";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useVoiceStore } from "@/stores/voiceStore";
import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";
import { useEffect, useRef, useState } from "react";
import AudioSettingsHeader from "./components/header";
import MicrophoneSelect from "./components/microphone-select";
import VoiceSelect from "./components/voice-select";

interface SettingsVoiceModalProps {
  children?: React.ReactNode;
  open?: boolean;
  userOpenaiApiKey?: string;
  userElevenLabsApiKey?: string;
  hasElevenLabsApiKeyEnv?: boolean;
  setShowSettingsModal: (
    open: boolean,
    openaiApiKey: string,
    elevenLabsApiKey: string,
  ) => void;
  hasOpenAIAPIKey: boolean;
}

const SettingsVoiceModal = ({
  children,
  open: initialOpen = false,
  userOpenaiApiKey,
  userElevenLabsApiKey,
  setShowSettingsModal,
  hasOpenAIAPIKey,
}: SettingsVoiceModalProps) => {
  const popupRef = useRef<HTMLDivElement>(null);
  const [voice, setVoice] = useState<string>("alloy");
  const [open, setOpen] = useState<boolean>(initialOpen);
  const voices = useVoiceStore((state) => state.voices);
  const shouldFetchVoices = voices.length === 0;
  const [openaiApiKey, setOpenaiApiKey] = useState<string>(
    userOpenaiApiKey ?? "",
  );
  const [elevenLabsApiKey, setElevenLabsApiKey] = useState<string>(
    userElevenLabsApiKey ?? "",
  );

  const globalVariables = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );

  const openaiVoices = useVoiceStore((state) => state.openaiVoices);
  const [allVoices, setAllVoices] = useState<
    {
      name: string;
      value: string;
    }[]
  >([]);

  const {
    data: voiceList,
    isFetched,
    refetch,
  } = useGetVoiceList({
    enabled: shouldFetchVoices,
    refetchOnMount: shouldFetchVoices,
    refetchOnWindowFocus: shouldFetchVoices,
    staleTime: Infinity,
  });

  const [microphones, setMicrophones] = useState<MediaDeviceInfo[]>([]);
  const [selectedMicrophone, setSelectedMicrophone] = useState<string>("");

  useEffect(() => {
    if (isFetched) {
      if (voiceList) {
        const allVoicesMerged = [...openaiVoices, ...voiceList];

        voiceList.length > 0
          ? setAllVoices(allVoicesMerged)
          : setAllVoices(openaiVoices);
      } else {
        setAllVoices(openaiVoices);
      }
    }
  }, [voiceList, isFetched, userElevenLabsApiKey]);

  useEffect(() => {
    const audioSettings = JSON.parse(
      getLocalStorage("lf_audio_settings_playground") || "{}",
    );
    if (isFetched) {
      if (audioSettings.provider) {
        setVoice(audioSettings.voice);
      } else {
        setVoice(openaiVoices[0].value);
      }
    } else {
      setVoice(openaiVoices[0].value);
    }
  }, [initialOpen, isFetched]);

  const handleSetVoice = (value: string) => {
    setVoice(value);
    const isOpenAiVoice = openaiVoices.some((voice) => voice.value === value);
    if (isOpenAiVoice) {
      setLocalStorage(
        "lf_audio_settings_playground",
        JSON.stringify({
          provider: "openai",
          voice: value,
        }),
      );
    } else {
      setLocalStorage(
        "lf_audio_settings_playground",
        JSON.stringify({
          provider: "elevenlabs",
          voice: value,
        }),
      );
    }
  };

  const handleSetOpen = (open: boolean) => {
    setOpen(open);
    setShowSettingsModal(open, openaiApiKey, elevenLabsApiKey);
  };

  const checkIfGlobalVariableExists = (variable: string) => {
    return globalVariables?.map((variable) => variable).includes(variable);
  };

  const handleSetMicrophone = (deviceId: string) => {
    setSelectedMicrophone(deviceId);
    localStorage.setItem("lf_selected_microphone", deviceId);
  };

  useEffect(() => {
    setOpenaiApiKey(userOpenaiApiKey ?? "");
  }, [userOpenaiApiKey]);

  useEffect(() => {
    setElevenLabsApiKey(userElevenLabsApiKey ?? "");

    if (!userElevenLabsApiKey) {
      handleSetVoice(openaiVoices[0].value);
      setAllVoices(openaiVoices);
      return;
    }

    refetch();
  }, [userElevenLabsApiKey]);

  useEffect(() => {
    if (!hasOpenAIAPIKey) {
      setOpen(true);
    }
  }, [initialOpen]);

  return (
    <>
      <DropdownMenu open={open} onOpenChange={handleSetOpen}>
        <DropdownMenuTrigger>{children}</DropdownMenuTrigger>
        <DropdownMenuContent
          className="w-[324px] rounded-xl shadow-lg"
          sideOffset={18}
          alignOffset={-55}
          align="end"
        >
          <div ref={popupRef} className="rounded-3xl">
            <div>
              <AudioSettingsHeader />
              <Separator className="w-full" />

              <div className="w-full space-y-4 p-4">
                <div className="grid w-full items-center gap-2">
                  <span className="flex items-center text-sm">
                    OpenAI API Key
                    <span className="ml-1 text-destructive">*</span>
                    <ShadTooltip content="OpenAI API key is required to use the voice assistant.">
                      <div>
                        <IconComponent
                          name="Info"
                          strokeWidth={2}
                          className="relative -top-[3px] left-1 h-[14px] w-[14px] text-placeholder"
                        />
                      </div>
                    </ShadTooltip>
                  </span>

                  <InputComponent
                    isObjectOption={false}
                    password={false}
                    nodeStyle
                    popoverWidth="16rem"
                    placeholder={getPlaceholder(
                      false,
                      "Enter your OpenAI API key",
                    )}
                    id="openai-api-key"
                    options={globalVariables?.map((variable) => variable) ?? []}
                    optionsPlaceholder={"Global Variables"}
                    optionsIcon="Globe"
                    optionsButton={<GeneralGlobalVariableModal />}
                    optionButton={(option) => (
                      <GeneralDeleteConfirmationModal
                        option={option}
                        onConfirmDelete={() => {}}
                      />
                    )}
                    value={openaiApiKey}
                    onChange={(value) => {
                      setOpenaiApiKey(value);
                    }}
                    selectedOption={
                      checkIfGlobalVariableExists(openaiApiKey)
                        ? openaiApiKey
                        : ""
                    }
                    setSelectedOption={setOpenaiApiKey}
                  />
                </div>

                <div className="grid w-full items-center gap-2">
                  <span className="flex items-center text-sm">
                    ElevenLabs API Key
                    <ShadTooltip content="If you have an ElevenLabs API key, you can select ElevenLabs voices.">
                      <div>
                        <IconComponent
                          name="Info"
                          strokeWidth={2}
                          className="relative -top-[3px] left-1 h-[14px] w-[14px] text-placeholder"
                        />
                      </div>
                    </ShadTooltip>
                  </span>

                  <InputComponent
                    isObjectOption={false}
                    password={false}
                    nodeStyle
                    popoverWidth="16rem"
                    placeholder={getPlaceholder(
                      false,
                      "Enter your ElevenLabs API key",
                    )}
                    id="eleven-labs-api-key"
                    options={globalVariables?.map((variable) => variable) ?? []}
                    optionsPlaceholder={"Global Variables"}
                    optionsIcon="Globe"
                    optionsButton={<GeneralGlobalVariableModal />}
                    optionButton={(option) => (
                      <GeneralDeleteConfirmationModal
                        option={option}
                        onConfirmDelete={() => {}}
                      />
                    )}
                    value={elevenLabsApiKey}
                    onChange={(value) => {
                      setElevenLabsApiKey(value);
                    }}
                    selectedOption={
                      checkIfGlobalVariableExists(elevenLabsApiKey)
                        ? elevenLabsApiKey
                        : ""
                    }
                    setSelectedOption={setElevenLabsApiKey}
                  />
                </div>

                <VoiceSelect
                  voice={voice}
                  handleSetVoice={handleSetVoice}
                  allVoices={allVoices}
                />

                <MicrophoneSelect
                  selectedMicrophone={selectedMicrophone}
                  handleSetMicrophone={handleSetMicrophone}
                  microphones={microphones}
                  setMicrophones={setMicrophones}
                  setSelectedMicrophone={setSelectedMicrophone}
                />
              </div>
            </div>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
};

export default SettingsVoiceModal;
