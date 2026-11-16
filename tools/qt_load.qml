// Loads every animation given after "--" as "<url>|<ip>|<op>" in Qt's Lottie
// player and exits 0 only when each one reaches Ready with that frame range.
// `mise run test` drives it off-screen.
import QtQuick
import Qt.labs.lottieqt

Item {
    id: root
    width: 512
    height: 512

    readonly property var cases: {
        const args = Qt.application.arguments
        return args.slice(args.indexOf("--") + 1).map(a => {
            const [url, ip, op] = a.split("|")
            return { url: url, ip: Number(ip), op: Number(op) }
        })
    }
    property bool done: false

    function settle() {
        if (done)
            return
        for (let i = 0; i < players.count; ++i) {
            const p = players.itemAt(i)
            if (!p || p.status === LottieAnimation.Null || p.status === LottieAnimation.Loading)
                return
        }
        done = true
        let failed = 0
        for (let i = 0; i < players.count; ++i) {
            const p = players.itemAt(i)
            const c = cases[i]
            const ready = p.status === LottieAnimation.Ready
            const range = p.startFrame === c.ip && p.endFrame === c.op
            if (ready && range) {
                console.log("ok", c.url, "frames", p.startFrame + "-" + p.endFrame, "at", p.frameRate, "fps")
            } else {
                failed++
                console.error("FAIL", c.url, ready ? "frames " + p.startFrame + "-" + p.endFrame
                              + ", expected " + c.ip + "-" + c.op : "did not reach Ready (status " + p.status + ")")
            }
        }
        Qt.exit(failed === 0 && cases.length > 0 ? 0 : 1)
    }

    Repeater {
        id: players
        model: root.cases
        delegate: LottieAnimation {
            required property var modelData
            source: modelData.url
            autoPlay: false
            onStatusChanged: root.settle()
        }
    }

    Component.onCompleted: Qt.callLater(root.settle)

    Timer {
        interval: 20000
        running: true
        onTriggered: {
            console.error("FAIL: Qt's Lottie player did not finish loading within 20 s")
            Qt.exit(1)
        }
    }
}
