package main

import "testing"

func TestMergeManagedClaimMappingsPreservesUnmanaged(t *testing.T) {
	existing := []claimMapping{
		{Claim: "groups", Value: "admins", Roles: []string{"access"}},
		{Claim: "groups", Value: "project-old-member", Roles: []string{"mustelinet-project-old-member"}},
	}
	desired := []claimMapping{
		{Claim: "groups", Value: "project-otterlab-member", Roles: []string{"mustelinet-project-otterlab-member"}},
	}

	merged := mergeManagedClaimMappings(existing, desired, "mustelinet-project-")

	if len(merged) != 2 {
		t.Fatalf("expected 2 mappings, got %d", len(merged))
	}
	if merged[0].Value != "admins" {
		t.Fatalf("expected unmanaged mapping to be preserved first, got %q", merged[0].Value)
	}
	if merged[1].Value != "project-otterlab-member" {
		t.Fatalf("expected desired mapping to replace managed mappings, got %q", merged[1].Value)
	}
}

func TestBuildOpenSSHNode(t *testing.T) {
	node, err := buildNode(nodePayload{
		Name:     "node-id",
		Hostname: "web01",
		Address:  "10.0.0.10",
		Port:     22,
		Labels: map[string]string{
			"mustelinet.io/managed-by": "openstack-teleport-reconciler",
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if !node.IsOpenSSHNode() {
		t.Fatal("expected OpenSSH node")
	}
	if node.GetAddr() != "10.0.0.10:22" {
		t.Fatalf("unexpected addr %q", node.GetAddr())
	}
}

func TestBuildRole(t *testing.T) {
	role, err := buildRole(rolePayload{
		Name:        "mustelinet-project-otterlab-member",
		ProjectID:   "p1",
		ProjectName: "otterlab",
		ProjectRole: "member",
		Logins:      []string{"ubuntu"},
		NodeLabels:  map[string]string{"mustelinet.io/project-id": "p1"},
		ManagedBy:   "openstack-teleport-reconciler",
	})
	if err != nil {
		t.Fatal(err)
	}
	if got := role.GetMetadata().Labels["mustelinet.io/managed-by"]; got != "openstack-teleport-reconciler" {
		t.Fatalf("unexpected managed-by label %q", got)
	}
	if got := role.GetLogins(true); len(got) != 1 || got[0] != "ubuntu" {
		t.Fatalf("unexpected logins %#v", got)
	}
}
