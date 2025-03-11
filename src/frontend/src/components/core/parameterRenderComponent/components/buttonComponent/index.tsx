import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";

import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "@/utils/utils";
import { useEffect, useRef, useState } from "react";
import { ReactSortable } from "react-sortablejs";

type ButtonComponentProps = {
  tooltip?: string;
  type: "tool_name" | "actions" | undefined;
  name?: string;
};

const ButtonComponent = ({
  tooltip = "",
  type,
  name,
}: ButtonComponentProps) => {
  const isDropdown = type !== "actions";
  const [open, setOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(isDropdown);

  const handleAuthButtonClick = () => {
    window.open("https://en.wikipedia.org/wiki/DataStax", "_blank");
    // setIsAuthenticated(!isAuthenticated);
  };

  const initialActionData = [
    {
      name: "Accept a repository invitation",
      id: 1,
    },
    {
      name: "Add an email address for the repository",
      id: 2,
    },
    {
      name: "Add assignee to an issue",
      id: 3,
    },
  ];

  const [actionData, setActionData] = useState(initialActionData);

  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex w-full flex-row gap-2">
        <Button
          variant={isDropdown ? "outline" : "default"}
          size="xs"
          onClick={() => setOpen(true)}
          className="w-full py-2"
        >
          {isDropdown ? (
            <div className="flex w-full items-center justify-start text-sm">
              {name || "Select a tool..."}
              <ForwardedIconComponent
                name="ChevronsUpDown"
                className="ml-auto h-5 w-5"
              />
            </div>
          ) : (
            <div className="flex items-center text-sm font-semibold">
              {name || "Select action"}
            </div>
          )}
        </Button>
        {isAuthenticated && (
          <Button
            size="icon"
            variant="warning"
            className="h-9 w-10 rounded-md border border-accent-amber-foreground"
            onClick={handleAuthButtonClick}
          >
            <ForwardedIconComponent
              name="unplug"
              className="h-5 w-5 text-accent-amber-foreground"
            />
          </Button>
        )}
      </div>

      {!isDropdown && (
        <div className="flex w-full flex-col">
          <ReactSortable
            list={actionData}
            setList={setActionData}
            className="flex w-full flex-col"
          >
            {actionData.map((data, index) => (
              <li
                key={data?.id}
                className="group inline-flex h-12 w-full cursor-grab items-center gap-2 text-sm font-medium text-gray-800"
              >
                <ForwardedIconComponent
                  name="grid-horizontal"
                  className="h-5 w-5 fill-gray-300 text-gray-300"
                />

                <div className="flex w-full items-center gap-x-2">
                  <div className="flex h-5 w-5 items-center justify-center rounded-full bg-gray-400 text-center text-white">
                    {index + 1}
                  </div>

                  <span className="max-w-48 truncate text-primary">
                    {data.name}
                  </span>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  className="ml-auto h-7 w-7 opacity-0 transition-opacity duration-200 hover:bg-red-100 hover:opacity-100"
                  onClick={() => {
                    setActionData(actionData.filter((_, i) => i !== index));
                  }}
                >
                  <ForwardedIconComponent
                    name="x"
                    className="h-6 w-6 text-red-500"
                  />
                </Button>
              </li>
            ))}
          </ReactSortable>
        </div>
      )}

      <ListSelectionComponent open={open} onClose={() => setOpen(false)} />
    </div>
  );
};

export default ButtonComponent;
