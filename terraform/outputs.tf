output "server_ip" {
  value = hcloud_server.k3s.ipv4_address
}

output "get_kubeconfig" {
  description = "Run this to fetch the kubeconfig"
  value       = "scp root@${hcloud_server.k3s.ipv4_address}:/etc/rancher/k3s/k3s.yaml ./kubeconfig && sed -i 's/127.0.0.1/${hcloud_server.k3s.ipv4_address}/' ./kubeconfig"
}
