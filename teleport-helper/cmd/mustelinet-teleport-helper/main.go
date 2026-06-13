package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/gravitational/teleport/api/client"
	"github.com/gravitational/teleport/api/types"
	"github.com/gravitational/teleport/api/utils"
)

const defaultNamespace = "default"

type request struct {
	Command           string              `json:"command"`
	ProxyAddr         string              `json:"proxy_addr,omitempty"`
	IdentityFile      string              `json:"identity_file,omitempty"`
	ManagedBy         string              `json:"managed_by,omitempty"`
	ManagedRolePrefix string              `json:"managed_role_prefix,omitempty"`
	ConnectorName     string              `json:"connector_name,omitempty"`
	Node              *nodePayload        `json:"node,omitempty"`
	Role              *rolePayload        `json:"role,omitempty"`
	OIDCMappings      *oidcMappingPayload `json:"oidc_mappings,omitempty"`
}

type response struct {
	OK           bool                `json:"ok"`
	Error        string              `json:"error,omitempty"`
	Nodes        []nodePayload       `json:"nodes,omitempty"`
	Roles        []rolePayload       `json:"roles,omitempty"`
	OIDCMappings *oidcMappingPayload `json:"oidc_mappings,omitempty"`
}

type nodePayload struct {
	Name        string            `json:"name"`
	Hostname    string            `json:"hostname"`
	SourceID    string            `json:"source_id"`
	ProjectID   string            `json:"project_id"`
	ProjectName string            `json:"project_name"`
	Region      string            `json:"region"`
	Labels      map[string]string `json:"labels"`
	Logins      []string          `json:"logins,omitempty"`
	Address     string            `json:"address,omitempty"`
	Port        int               `json:"port"`
}

type rolePayload struct {
	Name        string            `json:"name"`
	ProjectID   string            `json:"project_id"`
	ProjectName string            `json:"project_name"`
	ProjectRole string            `json:"project_role"`
	Logins      []string          `json:"logins"`
	NodeLabels  map[string]string `json:"node_labels"`
	ManagedBy   string            `json:"managed_by"`
}

type oidcMappingPayload struct {
	Name     string         `json:"name"`
	Mappings []claimMapping `json:"mappings"`
}

type claimMapping struct {
	Claim string   `json:"claim"`
	Value string   `json:"value"`
	Roles []string `json:"roles"`
}

func main() {
	req, err := decodeRequest(os.Stdin)
	if err != nil {
		encodeResponse(response{OK: false, Error: err.Error()})
		os.Exit(1)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	resp, err := handle(ctx, req)
	if err != nil {
		encodeResponse(response{OK: false, Error: err.Error()})
		os.Exit(1)
	}
	encodeResponse(resp)
}

func decodeRequest(reader io.Reader) (request, error) {
	var req request
	decoder := json.NewDecoder(reader)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		return request{}, err
	}
	if strings.TrimSpace(req.Command) == "" {
		return request{}, errors.New("command is required")
	}
	return req, nil
}

func encodeResponse(resp response) {
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	_ = encoder.Encode(resp)
}

func handle(ctx context.Context, req request) (response, error) {
	if req.Command == "health" {
		return response{OK: true}, nil
	}

	clt, err := newClient(ctx, req)
	if err != nil {
		return response{}, err
	}
	defer clt.Close()

	switch req.Command {
	case "list-nodes":
		nodes, err := clt.GetNodes(ctx, defaultNamespace)
		if err != nil {
			return response{}, err
		}
		return response{OK: true, Nodes: filterNodes(nodes, req.ManagedBy)}, nil
	case "upsert-node":
		if req.Node == nil {
			return response{}, errors.New("node is required")
		}
		node, err := buildNode(*req.Node)
		if err != nil {
			return response{}, err
		}
		if _, err := clt.UpsertNode(ctx, node); err != nil {
			return response{}, err
		}
		return response{OK: true}, nil
	case "delete-node":
		if req.Node == nil {
			return response{}, errors.New("node is required")
		}
		return response{OK: true}, clt.DeleteNode(ctx, defaultNamespace, req.Node.Name)
	case "list-roles":
		roles, err := clt.GetRoles(ctx)
		if err != nil {
			return response{}, err
		}
		return response{OK: true, Roles: filterRoles(roles, req.ManagedBy)}, nil
	case "upsert-role":
		if req.Role == nil {
			return response{}, errors.New("role is required")
		}
		role, err := buildRole(*req.Role)
		if err != nil {
			return response{}, err
		}
		if _, err := clt.UpsertRole(ctx, role); err != nil {
			return response{}, err
		}
		return response{OK: true}, nil
	case "delete-role":
		if req.Role == nil {
			return response{}, errors.New("role is required")
		}
		return response{OK: true}, clt.DeleteRole(ctx, req.Role.Name)
	case "get-oidc-connector":
		mappings, err := getManagedOIDCMappings(ctx, clt, req.ConnectorName, req.ManagedRolePrefix)
		if err != nil {
			return response{}, err
		}
		return response{OK: true, OIDCMappings: mappings}, nil
	case "upsert-oidc-connector":
		if req.OIDCMappings == nil {
			return response{}, errors.New("oidc_mappings is required")
		}
		if err := upsertManagedOIDCMappings(ctx, clt, *req.OIDCMappings, req.ManagedRolePrefix); err != nil {
			return response{}, err
		}
		return response{OK: true}, nil
	default:
		return response{}, fmt.Errorf("unsupported command %q", req.Command)
	}
}

func newClient(ctx context.Context, req request) (*client.Client, error) {
	if strings.TrimSpace(req.ProxyAddr) == "" {
		return nil, errors.New("proxy_addr is required")
	}
	if strings.TrimSpace(req.IdentityFile) == "" {
		return nil, errors.New("identity_file is required")
	}
	return client.New(ctx, client.Config{
		Addrs:       []string{req.ProxyAddr},
		Credentials: []client.Credentials{client.LoadIdentityFile(req.IdentityFile)},
	})
}

func filterNodes(nodes []types.Server, managedBy string) []nodePayload {
	payloads := make([]nodePayload, 0)
	for _, node := range nodes {
		labels := node.GetLabels()
		if managedBy != "" && labels["mustelinet.io/managed-by"] != managedBy {
			continue
		}
		payloads = append(payloads, nodeFromTeleport(node))
	}
	return payloads
}

func buildNode(payload nodePayload) (types.Server, error) {
	if payload.Port == 0 {
		payload.Port = 22
	}
	addr := net.JoinHostPort(payload.Address, strconv.Itoa(payload.Port))
	return types.NewNode(
		payload.Name,
		types.SubKindOpenSSHNode,
		types.ServerSpecV2{
			Addr:     addr,
			Hostname: payload.Hostname,
		},
		payload.Labels,
	)
}

func nodeFromTeleport(node types.Server) nodePayload {
	host, portText, _ := net.SplitHostPort(node.GetAddr())
	port, _ := strconv.Atoi(portText)
	if port == 0 {
		port = 22
	}
	labels := node.GetLabels()
	return nodePayload{
		Name:        node.GetName(),
		Hostname:    node.GetHostname(),
		SourceID:    labels["mustelinet.io/source-id"],
		ProjectID:   labels["mustelinet.io/project-id"],
		ProjectName: labels["mustelinet.io/project-name"],
		Region:      labels["mustelinet.io/region"],
		Labels:      labels,
		Address:     host,
		Port:        port,
	}
}

func filterRoles(roles []types.Role, managedBy string) []rolePayload {
	payloads := make([]rolePayload, 0)
	for _, role := range roles {
		labels := role.GetMetadata().Labels
		if managedBy != "" && labels["mustelinet.io/managed-by"] != managedBy {
			continue
		}
		payloads = append(payloads, roleFromTeleport(role))
	}
	return payloads
}

func buildRole(payload rolePayload) (types.Role, error) {
	role, err := types.NewRole(payload.Name, types.RoleSpecV6{})
	if err != nil {
		return nil, err
	}
	role.SetMetadata(types.Metadata{
		Name: payload.Name,
		Labels: map[string]string{
			"mustelinet.io/managed-by":    payload.ManagedBy,
			"mustelinet.io/project-id":    payload.ProjectID,
			"mustelinet.io/project-name":  payload.ProjectName,
			"mustelinet.io/project-role":  payload.ProjectRole,
			"mustelinet.io/source-system": "openstack",
		},
	})
	role.SetLogins(types.Allow, payload.Logins)
	role.SetNodeLabels(types.Allow, labelsToTeleport(payload.NodeLabels))
	return role, nil
}

func roleFromTeleport(role types.Role) rolePayload {
	metadata := role.GetMetadata()
	labels := metadata.Labels
	return rolePayload{
		Name:        role.GetName(),
		ProjectID:   labels["mustelinet.io/project-id"],
		ProjectName: labels["mustelinet.io/project-name"],
		ProjectRole: labels["mustelinet.io/project-role"],
		Logins:      role.GetLogins(types.Allow),
		NodeLabels:  labelsFromTeleport(role.GetNodeLabels(types.Allow)),
		ManagedBy:   labels["mustelinet.io/managed-by"],
	}
}

func labelsToTeleport(labels map[string]string) types.Labels {
	out := make(types.Labels, len(labels))
	for key, value := range labels {
		out[key] = utils.Strings{value}
	}
	return out
}

func labelsFromTeleport(labels types.Labels) map[string]string {
	out := make(map[string]string, len(labels))
	for key, values := range labels {
		if len(values) > 0 {
			out[key] = values[0]
		}
	}
	return out
}

func getManagedOIDCMappings(
	ctx context.Context,
	clt *client.Client,
	connectorName string,
	managedRolePrefix string,
) (*oidcMappingPayload, error) {
	if strings.TrimSpace(connectorName) == "" {
		return nil, errors.New("connector_name is required")
	}
	connector, err := clt.GetOIDCConnector(ctx, connectorName, true)
	if err != nil {
		return nil, err
	}
	return &oidcMappingPayload{
		Name:     connectorName,
		Mappings: filterManagedClaimMappings(claimMappingsFromTeleport(connector.GetClaimsToRoles()), managedRolePrefix),
	}, nil
}

func upsertManagedOIDCMappings(
	ctx context.Context,
	clt *client.Client,
	payload oidcMappingPayload,
	managedRolePrefix string,
) error {
	if strings.TrimSpace(payload.Name) == "" {
		return errors.New("oidc_mappings.name is required")
	}
	connector, err := clt.GetOIDCConnector(ctx, payload.Name, true)
	if err != nil {
		return err
	}
	existing := claimMappingsFromTeleport(connector.GetClaimsToRoles())
	merged := mergeManagedClaimMappings(existing, payload.Mappings, managedRolePrefix)
	connector.SetClaimsToRoles(claimMappingsToTeleport(merged))
	_, err = clt.UpsertOIDCConnector(ctx, connector)
	return err
}

func claimMappingsFromTeleport(mappings []types.ClaimMapping) []claimMapping {
	out := make([]claimMapping, 0, len(mappings))
	for _, mapping := range mappings {
		out = append(out, claimMapping{
			Claim: mapping.Claim,
			Value: mapping.Value,
			Roles: append([]string(nil), mapping.Roles...),
		})
	}
	return out
}

func claimMappingsToTeleport(mappings []claimMapping) []types.ClaimMapping {
	out := make([]types.ClaimMapping, 0, len(mappings))
	for _, mapping := range mappings {
		out = append(out, types.ClaimMapping{
			Claim: mapping.Claim,
			Value: mapping.Value,
			Roles: append([]string(nil), mapping.Roles...),
		})
	}
	return out
}

func filterManagedClaimMappings(mappings []claimMapping, managedRolePrefix string) []claimMapping {
	out := make([]claimMapping, 0)
	for _, mapping := range mappings {
		if mappingIsManaged(mapping, managedRolePrefix) {
			out = append(out, mapping)
		}
	}
	return out
}

func mergeManagedClaimMappings(
	existing []claimMapping,
	desired []claimMapping,
	managedRolePrefix string,
) []claimMapping {
	merged := make([]claimMapping, 0, len(existing)+len(desired))
	for _, mapping := range existing {
		if !mappingIsManaged(mapping, managedRolePrefix) {
			merged = append(merged, mapping)
		}
	}
	return append(merged, desired...)
}

func mappingIsManaged(mapping claimMapping, managedRolePrefix string) bool {
	if managedRolePrefix == "" || len(mapping.Roles) == 0 {
		return false
	}
	for _, role := range mapping.Roles {
		if !strings.HasPrefix(role, managedRolePrefix) {
			return false
		}
	}
	return true
}
