import { useLocation } from "react-router-dom";
import { FolderType } from "../../pages/MainPage/entities";
import { useFolderStore } from "../../stores/foldersStore";
import { cn } from "../../utils/utils";
import HorizontalScrollFadeComponent from "../horizontalScrollFadeComponent";
import SideBarButtonsComponent from "./components/sideBarButtons";
import SideBarFoldersButtonsComponent from "./components/sideBarFolderButtons";
import { addFolder } from "../../pages/MainPage/services";
import { useNavigate } from "react-router-dom";

const navigate = useNavigate();

type SidebarNavProps = {
  items: {
    href?: string;
    title: string;
    icon: React.ReactNode;
  }[];
  handleOpenNewFolderModal?: () => void;
  handleChangeFolder?: (id: string) => void;
  handleEditFolder?: (item: FolderType) => void;
  handleDeleteFolder?: (item: FolderType) => void;
  className?: string;
};

export default function SidebarNav({
  className,
  items,
  handleChangeFolder,
  handleEditFolder,
  handleDeleteFolder,
  ...props
}: SidebarNavProps) {
  const location = useLocation();
  const pathname = location.pathname;
  const loadingFolders = useFolderStore((state) => state.loading);
  const folders = useFolderStore((state) => state.folders);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);

  const pathValues = ["folder", "components", "flows", "all"];
  const isFolderPath = pathValues.some((value) => pathname.includes(value));

  function addNewFolder() {
    addFolder({ name: "New Folder", parent_id: null, description: "" }).then(
      (res) => {
        getFoldersApi(true);
        navigate(`all/folder/${res.id}`, { state: { folderId: res.id } });
      },
    );
  }

  return (
    <nav className={cn(className)} {...props}>
      <HorizontalScrollFadeComponent>
        <SideBarButtonsComponent items={items} pathname={pathname} />

        {!loadingFolders && folders?.length > 0 && isFolderPath && (
          <SideBarFoldersButtonsComponent
            folders={folders}
            pathname={pathname}
            handleChangeFolder={handleChangeFolder}
            handleEditFolder={handleEditFolder}
            handleDeleteFolder={handleDeleteFolder}
            handleAddFolder={addNewFolder}
          />
        )}
      </HorizontalScrollFadeComponent>
    </nav>
  );
}
