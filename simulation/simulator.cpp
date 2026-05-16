#include <iostream>
#include <cstring>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <cstdio>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <poll.h>
#include <arpa/inet.h>
#include <sys/time.h>

static unsigned long now_ms() {
    struct timeval tv;
    gettimeofday(&tv, 0);
    return (unsigned long)tv.tv_sec * 1000 + (unsigned long)tv.tv_usec / 1000;
}

typedef unsigned char byte;

// ========== MINIMAL MQTT CLIENT ==========
class MQTT {
    int sock;
    char rbuf[4096];
    int rlen;

    int remaining_len() {
        int m = 1, v = 0;
        for (int i = 0; i < 4; i++) {
            if (rlen <= 0) return -1;
            byte b = rbuf[rlen - 1]; rlen--;
            v += (b & 0x7F) * m;
            m *= 128;
            if (!(b & 0x80)) break;
        }
        return v;
    }

public:
    MQTT() : sock(-1), rlen(0) {}

    bool connect(const char* host, int port, const char* cid) {
        struct addrinfo hints, *res;
        memset(&hints, 0, sizeof(hints));
        hints.ai_family = AF_UNSPEC;
        hints.ai_socktype = SOCK_STREAM;
        char port_str[8];
        snprintf(port_str, sizeof(port_str), "%d", port);
        int gai = getaddrinfo(host, port_str, &hints, &res);
        if (gai != 0) { fprintf(stderr, "DNS fail\n"); return false; }
        sock = -1;
        for (struct addrinfo* rp = res; rp; rp = rp->ai_next) {
            int fd = ::socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
            if (fd < 0) continue;
            if (::connect(fd, rp->ai_addr, rp->ai_addrlen) >= 0) { sock = fd; break; }
            close(fd);
        }
        freeaddrinfo(res);
        if (sock < 0) { fprintf(stderr, "Connect fail\n"); return false; }
        // CONNECT packet
        int clen = strlen(cid);
        byte packet[256];
        int p = 0;
        packet[p++] = 0x10; // CONNECT
        int rl = 12 + clen;
        packet[p++] = rl;
        packet[p++] = 0; packet[p++] = 4; memcpy(packet+p, "MQTT", 4); p += 4;
        packet[p++] = 4;  // level
        packet[p++] = 2;  // clean session
        packet[p++] = 0; packet[p++] = 60; // keepalive
        packet[p++] = (clen >> 8) & 0xFF; packet[p++] = clen & 0xFF;
        memcpy(packet+p, cid, clen); p += clen;
        // Send all bytes (loop in case of partial send)
        int total = 0;
        while (total < p) {
            int n = send(sock, packet + total, p - total, 0);
            if (n <= 0) { fprintf(stderr, "send fail\n"); return false; }
            total += n;
        }
        // Read CONNACK with timeout
        rlen = 0;
        unsigned long deadline = now_ms() + 5000;
        while (rlen < 4) {
            unsigned long now = now_ms();
            if (now > deadline) { fprintf(stderr, "CONNACK timeout\n"); return false; }
            struct pollfd pfd = {sock, POLLIN, 0};
            int pr = poll(&pfd, 1, deadline - now);
            if (pr <= 0) continue;
            int n = read(sock, rbuf + rlen, sizeof(rbuf) - rlen);
            if (n <= 0) { fprintf(stderr, "CONNACK recv fail\n"); return false; }
            rlen += n;
        }
        if (rbuf[0] != 0x20 || rbuf[3] != 0) {
            fprintf(stderr, "CONNACK rejected (rc=%d)\n", rbuf[3]);
            return false;
        }
        printf("MQTT connected\n");
        return true;
    }

    bool publish(const char* topic, const char* payload) {
        int tlen = strlen(topic), plen = strlen(payload);
        byte packet[8192];
        int p = 0;
        packet[p++] = 0x30; // PUBLISH QoS 0
        int rl = 2 + tlen + plen;
        if (rl < 128) packet[p++] = rl;
        else { packet[p++] = (rl % 128) | 0x80; packet[p++] = rl / 128; }
        packet[p++] = (tlen >> 8) & 0xFF; packet[p++] = tlen & 0xFF;
        memcpy(packet+p, topic, tlen); p += tlen;
        memcpy(packet+p, payload, plen); p += plen;
        int total = 0;
        while (total < p) {
            int n = send(sock, packet + total, p - total, 0);
            if (n <= 0) return false;
            total += n;
        }
        return true;
    }

    bool subscribe(const char* topic) {
        int tlen = strlen(topic);
        byte packet[256];
        int p = 0;
        packet[p++] = 0x82; // SUBSCRIBE
        int rl = 2 + 2 + tlen + 1;
        packet[p++] = rl;
        packet[p++] = 0; packet[p++] = 1; // packet ID
        packet[p++] = (tlen >> 8) & 0xFF; packet[p++] = tlen & 0xFF;
        memcpy(packet+p, topic, tlen); p += tlen;
        packet[p++] = 0; // QoS 0
        int total = 0;
        while (total < p) {
            int n = send(sock, packet + total, p - total, 0);
            if (n <= 0) return false;
            total += n;
        }
        return true;
    }

    int read_packet(byte* buf, int bufsz) {
        struct pollfd pfd = {sock, POLLIN, 0};
        if (poll(&pfd, 1, 100) <= 0) return 0;
        int n = ::read(sock, buf, bufsz);
        return n > 0 ? n : -1;
    }

    void ping() {
        byte pkt[2] = {0xC0, 0x00};
        send(sock, pkt, 2, 0);
    }

    void disconnect() { if (sock >= 0) { close(sock); sock = -1; } }
    ~MQTT() { disconnect(); }
};

// ========== SENSOR SIMULATION ==========
const char* TYPES[10]    = {"Temp","Vibration","Current","Light","Humidity","Ultrasonic","IR","Pressure","Smoke","Fire"};
const char* ZONES[10]    = {"A","A","A","A","B","B","B","C","C","C"};
const float BASES[10]    = {45, 2.5, 12, 500, 45, 2.0, 1.0, 101.3, 10, 5};
const char  PREFIXES[10] = {'T','V','C','L','H','U','I','P','S','F'};
const int SENSORS_PER_TYPE = 5;
const int NUM_TYPES = 10;
const int TOTAL_SENSORS = 50;
const float ANOMALY_RATIO = 1.3;
volatile bool g_running = true;

struct Sensor {
    char id[4];
    const char* type;
    const char* zone;
    float base;
    float cur;
    float overrideVal;
    unsigned long overrideUntil;
    const char* status;
    bool alerted;
};

Sensor sensors[TOTAL_SENSORS];

float gauss() {
    float s = 0;
    for (int i = 0; i < 12; i++) s += (rand() % 20001 - 10000) / 10000.0;
    return s / 12.0;
}

void init_sensors() {
    int idx = 0;
    for (int t = 0; t < NUM_TYPES; t++) {
        for (int i = 1; i <= SENSORS_PER_TYPE; i++) {
            Sensor& sn = sensors[idx];
            snprintf(sn.id, sizeof(sn.id), "%c%d", PREFIXES[t], i);
            sn.type   = TYPES[t];
            sn.zone   = ZONES[t];
            sn.base   = BASES[t];
            sn.cur    = sn.base;
            sn.overrideVal   = 0;
            sn.overrideUntil = 0;
            sn.status = "NORMAL";
            sn.alerted = false;
            idx++;
        }
    }
    printf("Init %d sensors\n", TOTAL_SENSORS);
}

void update_sensors(unsigned long now) {
    for (int i = 0; i < TOTAL_SENSORS; i++) {
        Sensor& s = sensors[i];
        if (s.overrideUntil > 0 && now < s.overrideUntil) {
            s.cur = s.overrideVal;
            s.status = "OVERRIDE";
            continue;
        }
        s.overrideUntil = 0;
        s.status = "NORMAL";
        s.alerted = false;
        float noise = gauss() * (s.base * 0.02);
        s.cur = s.base + noise;
        if (s.cur < 0) s.cur = 0;
        s.cur = roundf(s.cur * 100.0) / 100.0;
        if (s.base > 0 && (s.cur / s.base) > ANOMALY_RATIO) {
            s.status = "ANOMALY";
        }
    }
}

void build_json_all(char* buf, int bufsz) {
    int pos = 0;
    pos += snprintf(buf + pos, bufsz - pos, "[");
    for (int i = 0; i < TOTAL_SENSORS; i++) {
        Sensor& s = sensors[i];
        pos += snprintf(buf + pos, bufsz - pos,
            "%s{\"id\":\"%s\",\"type\":\"%s\",\"zone\":\"%s\",\"value\":%.2f,\"base\":%.1f,\"status\":\"%s\"}",
            (i > 0 ? "," : ""), s.id, s.type, s.zone, s.cur, s.base, s.status);
    }
    pos += snprintf(buf + pos, bufsz - pos, "]");
}

void build_alert_json(char* buf, int bufsz, Sensor& s) {
    snprintf(buf, bufsz,
        "{\"id\":\"%s\",\"type\":\"%s\",\"zone\":\"%s\",\"value\":%.2f,\"base\":%.1f,\"ratio\":%.2f,\"severity\":\"HIGH\",\"ts\":%lu}",
        s.id, s.type, s.zone, s.cur, s.base, s.cur / s.base, (unsigned long)(time(0) * 1000));
}

void handle_cmd(const char* msg, unsigned long now_ms) {
    printf("CMD: %s\n", msg);
    if (strcmp(msg, "FAULT_RANDOM_3") == 0) {
        bool picked[TOTAL_SENSORS] = {false};
        for (int n = 0; n < 3; n++) {
            int idx;
            do { idx = rand() % TOTAL_SENSORS; } while (picked[idx]);
            picked[idx] = true;
            Sensor& s = sensors[idx];
            s.overrideVal   = s.base * 1.6;
            s.overrideUntil = now_ms + 15000;
            s.cur = s.overrideVal;
            s.status = "OVERRIDE";
            printf("  Fault %s %.2f\n", s.id, s.overrideVal);
        }
    } else if (strcmp(msg, "FAULT_ALL") == 0) {
        for (int i = 0; i < TOTAL_SENSORS; i++) {
            Sensor& s = sensors[i];
            s.overrideVal   = s.base * 2.0;
            s.overrideUntil = now_ms + 15000;
            s.cur = s.overrideVal;
            s.status = "OVERRIDE";
        }
        printf("  Fault ALL\n");
    } else if (strncmp(msg, "OVERRIDE:", 9) == 0) {
        char sid[4]; float val; unsigned long dur;
        if (sscanf(msg + 9, "%3[^:]:%f:%lu", sid, &val, &dur) == 3) {
            for (int i = 0; i < TOTAL_SENSORS; i++) {
                if (strcmp(sensors[i].id, sid) == 0) {
                    sensors[i].overrideVal   = val;
                    sensors[i].overrideUntil = now_ms + dur * 1000;
                    sensors[i].cur = val;
                    sensors[i].status = "OVERRIDE";
                    printf("  Override %s = %.2f %lus\n", sid, val, dur);
                    break;
                }
            }
        }
    } else if (strcmp(msg, "CLEAR") == 0) {
        for (int i = 0; i < TOTAL_SENSORS; i++) {
            sensors[i].overrideUntil = 0;
            sensors[i].status = "NORMAL";
            sensors[i].alerted = false;
        }
        printf("  Clear all\n");
    } else if (strcmp(msg, "STOP") == 0) {
        printf("  STOP received -- shutting down\n");
        g_running = false;
    }
}

int main() {
    srand(time(0));
    printf("=== Smart Factory IoT - Native C++ Simulator ===\n");
    init_sensors();

    MQTT mqtt;
    if (!mqtt.connect("broker.emqx.io", 1883, "FactorySim-Native")) {
        std::cerr << "Failed to connect MQTT\n";
        return 1;
    }

    const char* TOPIC_SENSORS = "factory/sensors/all";
    const char* TOPIC_ALERTS  = "factory/sensors/alerts";
    const char* TOPIC_CMD     = "factory/sensors/cmd";

    mqtt.subscribe(TOPIC_CMD);
    printf("Subscribed to %s\n", TOPIC_CMD);

    unsigned long lastPub = 0;
    byte cmdBuf[512];

    while (g_running) {
        unsigned long now = now_ms();

        // Handle incoming commands
        int n = mqtt.read_packet(cmdBuf, sizeof(cmdBuf));
        if (n > 0 && cmdBuf[0] == 0x30) { // PUBLISH
            int p = 1;
            int rl = 0, m = 1;
            while (p < n && cmdBuf[p] & 0x80) {
                rl += (cmdBuf[p] & 0x7F) * m; m *= 128; p++;
            }
            if (p < n) rl += cmdBuf[p] & 0x7F; p++;
            if (p + 2 <= n) {
                int tlen = (cmdBuf[p] << 8) | cmdBuf[p+1]; p += 2;
                if (p + tlen <= n) {
                    cmdBuf[p + tlen] = '\0';
                    handle_cmd((const char*)(cmdBuf + p), now);
                }
            }
        }

        if (now - lastPub >= 1000) {
            update_sensors(now);

            // Publish all sensors
            char allBuf[8192];
            build_json_all(allBuf, sizeof(allBuf));
            mqtt.publish(TOPIC_SENSORS, allBuf);

            // Publish alerts
            for (int i = 0; i < TOTAL_SENSORS; i++) {
                Sensor& s = sensors[i];
                if (strcmp(s.status, "ANOMALY") == 0 && !s.alerted) {
                    s.alerted = true;
                    char alertBuf[512];
                    build_alert_json(alertBuf, sizeof(alertBuf), s);
                    mqtt.publish(TOPIC_ALERTS, alertBuf);
                    printf("Alert %s %.2f/%.2f\n", s.id, s.cur, s.base);
                }
            }

            printf("Pub %d sensors OK\n", TOTAL_SENSORS);
            lastPub = now;

            // Ping every 30s
            static unsigned long lastPing = 0;
            if (now - lastPing > 30000) {
                mqtt.ping();
                lastPing = now;
            }
        }

        usleep(50000); // 50ms
    }

    return 0;
}
