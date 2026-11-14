import {useQuery,useMutation,useQueryClient} from '@tanstack/react-query';
import {api} from '../api';
export function useApi(path,enabled=true){return useQuery({queryKey:[path],queryFn:()=>api(path),enabled,refetchInterval:10000});}
export function useAction(toast){const cache=useQueryClient();return useMutation({mutationFn:({path,method='POST',body})=>api(path,{method,body}),onSuccess:()=>cache.invalidateQueries(),onError:error=>toast(error.message)});}
