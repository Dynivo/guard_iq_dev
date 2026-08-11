import { useQuery, useMutation, type UseQueryOptions } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { AxiosError } from 'axios';

export function useApiQuery<T>(
  key: string[],
  url: string,
  options?: Omit<UseQueryOptions<T, AxiosError>, 'queryKey' | 'queryFn'>
) {
  return useQuery<T, AxiosError>({
    queryKey: key,
    queryFn: async () => {
      const response = await apiClient.get<T>(url);
      return response.data;
    },
    ...options,
  });
}

export function useApiMutation<TData, TVariables>(
  url: string,
  method: 'post' | 'put' | 'patch' | 'delete' = 'post'
) {
  return useMutation<TData, AxiosError, TVariables>({
    mutationFn: async (variables) => {
      const response = await apiClient[method]<TData>(url, variables);
      return response.data;
    },
  });
}
