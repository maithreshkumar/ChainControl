from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class NodeEnrollmentThrottle(AnonRateThrottle):
    scope = "node_enrollment"


class NodeStatusThrottle(SimpleRateThrottle):
    scope = "node_status"

    def get_cache_key(self, request, view):
        node = getattr(request, "auth", None)
        return self.cache_format % {"scope": self.scope, "ident": getattr(node, "node_uuid", self.get_ident(request))}


class NodeHeartbeatThrottle(NodeStatusThrottle):
    scope = "node_heartbeat"
