"""Sample KDMap for offline tests."""

from kdm.schema import (
    DecisionOption,
    KDMap,
    KDMNode,
    NodeType,
    Reversibility,
    Stage,
)


def sample_map() -> KDMap:
    return KDMap(
        mode="build",
        domain="Ứng dụng quản lý bãi đỗ xe",
        target_outcome="Chủ bãi xem slot trống realtime trên điện thoại",
        overview="Hệ thống IoT + app mobile cho bãi đỗ nhỏ.",
        flows=["Xe vào → cảm biến → server → app chủ bãi"],
        hard_constraints=["Phải hoạt động khi mất mạng ngắn"],
        out_of_scope=["Thanh toán online — chưa cần MVP"],
        stages=[
            Stage(id="s1", title="MVP cảm biến", order=1),
            Stage(id="s2", title="App mobile", order=2),
            Stage(id="s3", title="Vận hành", order=3),
        ],
        nodes=[
            KDMNode(
                id="owner",
                type=NodeType.actor,
                title="Chủ bãi",
                summary="Người theo dõi slot trống.",
                terminology=["slot — vị trí đỗ một xe"],
                stage_id="s1",
            ),
            KDMNode(
                id="db_choice",
                type=NodeType.decision,
                title="Chọn database",
                summary="Lưu trạng thái slot.",
                terminology=["SQLite — DB nhúng, một file"],
                stage_id="s1",
                depends_on=["owner"],
                options=[
                    DecisionOption(
                        name="SQLite",
                        pros=["Đơn giản"],
                        cons=["Khó scale"],
                        fit_reason="Hợp MVP <100 slot",
                    ),
                    DecisionOption(
                        name="PostgreSQL",
                        pros=["Scale tốt"],
                        cons=["Cần server"],
                        fit_reason="Dư sức cho MVP",
                    ),
                ],
                reversibility=Reversibility.painful,
                switch_trigger="Đổi khi >10k slot",
            ),
            KDMNode(
                id="sensor_ok",
                type=NodeType.checkpoint,
                title="Cảm biến hoạt động",
                summary="Đọc slot chính xác.",
                terminology=["MQTT — giao thức IoT nhẹ"],
                stage_id="s1",
                depends_on=["db_choice"],
                proof="Gắn 5 cảm biến, đo độ trễ <2s",
            ),
            KDMNode(
                id="label_special",
                type=NodeType.component,
                title='Module "API" & (gateway)',
                summary="Nhận dữ liệu cảm biến.",
                terminology=["gateway — cổng nối cảm biến lên server"],
                stage_id="s2",
                depends_on=["sensor_ok"],
            ),
        ],
    )
