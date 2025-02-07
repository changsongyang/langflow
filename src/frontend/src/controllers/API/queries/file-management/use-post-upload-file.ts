import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostUploadFile {
  file: File;
}

export const usePostUploadFileV2: useMutationFunctionType<
  undefined,
  IPostUploadFile
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postUploadFileFn = async (payload: IPostUploadFile): Promise<any> => {
    const formData = new FormData();
    formData.append("file", payload.file);
    const data = new Date().toISOString().split("Z")[0];

    const newFile = {
      id: "temp",
      name: payload.file.name.split(".").slice(0, -1).join("."),
      path: payload.file.name,
      size: payload.file.size,
      updated_at: data,
      created_at: data,
      progress: 0,
    };
    queryClient.setQueryData(["useGetFilesV2"], (old: any) => {
      return [...old, newFile];
    });

    const response = await api.post<any>(
      `${getURL("FILE_MANAGEMENT", {}, true)}/`,
      formData,
      {
        onUploadProgress: (progressEvent) => {
          if (progressEvent.progress) {
            queryClient.setQueryData(["useGetFilesV2"], (old: any) => {
              return old.map((file: any) => {
                if (file?.id === "temp") {
                  return { ...file, progress: progressEvent.progress };
                }
                return file;
              });
            });
          }
        },
      },
    );

    return response.data;
  };

  const mutation: UseMutationResult<IPostUploadFile, any, IPostUploadFile> =
    mutate(
      ["usePostUploadFileV2"],
      async (payload: IPostUploadFile) => {
        const res = await postUploadFileFn(payload);
        return res;
      },
      {
        onSettled: (data, error, variables, context) => {
          queryClient.invalidateQueries({
            queryKey: ["useGetFilesV2"],
          });
          options?.onSettled?.(data, error, variables, context);
        },
        ...options,
      },
    );

  return mutation;
};
