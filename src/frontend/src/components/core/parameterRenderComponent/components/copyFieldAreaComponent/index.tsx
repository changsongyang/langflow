import { GRADIENT_CLASS } from "@/constants/constants";
import { useRef, useState } from "react";
import { cn } from "../../../../../utils/utils";
import IconComponent from "../../../../common/genericIconComponent";
import { Input } from "../../../../ui/input";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputProps, TextAreaComponentType } from "../../types";

const inputClasses = {
  base: ({ isFocused }: { isFocused: boolean }) =>
    `w-full ${isFocused ? "" : "pr-3"}`,
  editNode: "input-edit-node",
  normal: ({ isFocused }: { isFocused: boolean }) =>
    `primary-input ${isFocused ? "text-primary" : "text-muted-foreground"}`,
  disabled: "disabled-state",
};

const externalLinkIconClasses = {
  gradient: ({
    disabled,
    editNode,
  }: {
    disabled: boolean;
    editNode: boolean;
  }) =>
    disabled
      ? ""
      : editNode
        ? "gradient-fade-input-edit-node"
        : "gradient-fade-input",
  background: ({
    disabled,
    editNode,
  }: {
    disabled: boolean;
    editNode: boolean;
  }) =>
    disabled
      ? ""
      : editNode
        ? "background-fade-input-edit-node"
        : "background-fade-input",
  icon: "icons-parameters-comp absolute right-3 h-4 w-4 shrink-0",
  editNodeTop: "top-[-1.4rem] h-5",
  normalTop: "top-[-2.1rem] h-7",
  iconTop: "top-[-1.7rem]",
};

export default function CopyFieldAreaComponent({
  value,
  disabled,
  handleOnNewValue,
  editNode = false,
  id = "",
  placeholder,
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const getInputClassName = () => {
    return cn(
      inputClasses.base({ isFocused }),
      editNode ? inputClasses.editNode : inputClasses.normal({ isFocused }),
      disabled && inputClasses.disabled,
      isFocused && "pr-10",
    );
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleOnNewValue({ value: e.target.value });
  };

  const handleCopy = (event?: React.MouseEvent<HTMLDivElement>) => {
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
    navigator.clipboard.writeText(value);
    event?.stopPropagation();
  };

  const renderIcon = () => (
    <div onClick={handleCopy}>
      {!disabled && (
        <div
          className={cn(
            externalLinkIconClasses.gradient({
              disabled,
              editNode,
            }),
            editNode
              ? externalLinkIconClasses.editNodeTop
              : externalLinkIconClasses.normalTop,
          )}
          style={{
            pointerEvents: "none",
            background: isFocused
              ? undefined
              : disabled
                ? "bg-background"
                : GRADIENT_CLASS,
          }}
          aria-hidden="true"
        />
      )}

      <IconComponent
        dataTestId={`btn_copy_${id?.toLowerCase()}${editNode ? "_advanced" : ""}`}
        name={isCopied ? "Check" : "Copy"}
        className={cn(
          "cursor-pointer bg-background",
          externalLinkIconClasses.icon,
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.iconTop,
          disabled
            ? "bg-muted text-placeholder-foreground"
            : "bg-background text-foreground",
        )}
      />
    </div>
  );

  return (
    <div className={cn("w-full", disabled && "pointer-events-none")}>
      <Input
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        id={id}
        data-testid={id}
        value={disabled ? "" : value}
        onChange={handleInputChange}
        disabled={disabled}
        className={getInputClassName()}
        placeholder={getPlaceholder(disabled, placeholder)}
        aria-label={disabled ? value : undefined}
        ref={inputRef}
        type="text"
      />
      <div className="relative w-full">{renderIcon()}</div>
    </div>
  );
}
