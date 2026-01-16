# ARQ Protocol Simulation - Proje Dokümantasyonu

**BLG 337E - Principles of Computer Communication**  
**Assignment 2: Cross-Layer Performance Optimization of a Custom ARQ Protocol**

---

## 1. Proje Genel Bakış

Bu proje, özel bir ağ simülatörü içinde **Selective Repeat ARQ** protokolünün tam bir implementasyonunu içerir. Simülatör, üç katmanlı bir mimari kullanarak uçtan uca veri iletimini modellemekte ve **Goodput** optimizasyonu için kapsamlı performans analizi sunmaktadır.

### 1.1 Mimari Diyagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION                               │
│                    (100 MB Test Data)                            │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                     TRANSPORT LAYER                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Segmentasyon│  │   CRC32     │  │  256KB Buffer + Flow    │  │
│  │  (L bytes)  │  │  Checksum   │  │  Control (Backpressure) │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                    8-byte Header                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                       LINK LAYER                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Selective  │  │  Adaptive   │  │    Fast Retransmit      │  │
│  │ Repeat ARQ  │  │   Timeout   │  │   (3 Duplicate ACKs)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                   24-byte Header                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                     PHYSICAL LAYER                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  10 Mbps    │  │  Gilbert-   │  │  Asymmetric Delays      │  │
│  │  Bit Rate   │  │  Elliot     │  │  (40ms/10ms prop)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Katman Detayları

### 2.1 Fiziksel Katman (`layers/physical.py`)

Fiziksel katman, kanal karakteristiklerini ve hata modelini simüle eder.

#### Parametreler

| Parametre | Değer | Açıklama |
|-----------|-------|----------|
| `BIT_RATE` | 10 Mbps | Kanal kapasitesi |
| `FORWARD_PROP_DELAY` | 40 ms | Veri yönünde yayılma gecikmesi |
| `REVERSE_PROP_DELAY` | 10 ms | ACK yönünde yayılma gecikmesi |
| `PROCESSING_DELAY` | 2 ms | Çerçeve başına işleme gecikmesi |

#### Gilbert-Elliot Hata Modeli

Kanal, iki durumlu Markov zinciri ile modellenir:

```
         P_G_TO_B = 0.002
    ┌──────────────────────┐
    │                      ▼
┌───────┐              ┌───────┐
│ GOOD  │              │  BAD  │
│BER=1e-6              │BER=5e-3
└───────┘              └───────┘
    ▲                      │
    └──────────────────────┘
         P_B_TO_G = 0.05
```

**Hata Hesaplama:**
- Her frame için: `P(error) = 1 - (1 - BER)^(frame_bits)`
- GOOD durumda: BER = 10⁻⁶ (neredeyse hatasız)
- BAD durumda: BER = 5×10⁻³ (yüksek hata oranı)

#### Gecikme Hesaplama

```python
Total_Delay = Transmission_Delay + Propagation_Delay + Processing_Delay
            = (frame_bytes × 8) / BIT_RATE + prop_delay + 2ms
```

---

### 2.2 Bağlantı Katmanı (`layers/link.py`)

Selective Repeat ARQ protokolünün tam implementasyonu.

#### Temel Özellikler

| Özellik | Açıklama |
|---------|----------|
| **Window Size (W)** | Değişken: {2, 4, 8, 16, 32, 64} |
| **Header Size** | 24 byte (seq_num + type + padding) |
| **Sequence Numbering** | Monoton artan integer |
| **Buffering** | Out-of-order paketler için alıcı buffer |

#### Gönderici Durumu

```python
send_base = 0           # Pencere başlangıcı
next_seq_num = 0        # Sonraki gönderilecek seq
send_window = {         # Gönderilen frame'lerin takibi
    seq: {
        'frame': Frame,
        'send_time': float,
        'acked': bool,
        'retransmitted': bool
    }
}
```

#### Alıcı Durumu

```python
recv_base = 0           # Beklenen sıradaki seq
recv_buffer = {         # Sıra dışı gelen paketler
    seq: (payload, checksum)
}
```

#### Adaptive Timeout (Jacobson's Algorithm)

RTT ölçümlerine dayalı dinamik timeout hesaplama:

```python
estimated_rtt = (1 - α) × estimated_rtt + α × sample_rtt     # α = 0.125
dev_rtt = (1 - β) × dev_rtt + β × |sample_rtt - estimated_rtt|  # β = 0.25
timeout = estimated_rtt + 4 × dev_rtt

# Güvenlik sınırları: 20ms ≤ timeout ≤ 500ms
```

**Karn's Algorithm:** Yeniden iletilen paketlerin RTT'si kullanılmaz.

#### Fast Retransmit

3 duplicate ACK alındığında timeout beklemeden anında yeniden iletim:

```python
if dup_ack_count >= 3:
    retransmit(send_base)  # En eski unacked paket
    dup_ack_count = 0
```

---

### 2.3 Taşıma Katmanı (`layers/transport.py`)

Uygulama verisi ile link katmanı arasında köprü görevi görür.

#### Segmentasyon

```python
# 100 MB veri → N adet segment
for i in range(0, len(data), L):
    segment = Segment(
        seq_num = i // L,
        data = data[i:i+L],
        header = 8 bytes  # seq_num + padding
    )
```

| Payload Size (L) | Segment Sayısı (100MB için) |
|------------------|----------------------------|
| 128 bytes | 819,200 |
| 256 bytes | 409,600 |
| 512 bytes | 204,800 |
| 1024 bytes | 102,400 |
| 2048 bytes | 51,200 |
| 4096 bytes | 25,600 |

#### Bütünlük Kontrolü (CRC32)

```python
def compute_checksum(data):
    return zlib.crc32(data) & 0xFFFFFFFF

def verify_integrity(data, expected):
    return compute_checksum(data) == expected
```

#### Buffer Yönetimi ve Backpressure

```
┌────────────────────────────────────────┐
│           256 KB Receiver Buffer        │
├────────────────────────────────────────┤
│ ████████████████████░░░░░░░░░░░░░░░░░░ │
│         current_usage    free_space    │
└────────────────────────────────────────┘
        │
        ▼
   if usage > 80%:
       → Delayed ACK (10ms)
       → Backpressure to sender

   if buffer_full:
       → Reject incoming segment
       → Sender will timeout & retransmit
```

#### Uygulama Tüketimi

```python
def app_consume(max_bytes):
    # Her 1ms'de 10Mbps / 8 = 1.25 KB tüketim
    # In-order segmentleri buffer'dan çıkar
    while next_expected in buffer and consumed < max_bytes:
        deliver_to_app(buffer[next_expected])
        next_expected += 1
```

---

## 3. Simülasyon Motoru (`engine.py`)

Event-driven (olay güdümlü) simülasyon mimarisi.

### 3.1 Event Türleri

| Event | Açıklama |
|-------|----------|
| `DATA_ARRIVE` | Veri frame'i alıcıya ulaştı |
| `ACK_ARRIVE` | ACK gönderene ulaştı |
| `APP_CONSUME` | Uygulama buffer'dan veri tüketiyor (1ms periyot) |
| `DELAYED_ACK` | Geciktirilmiş ACK gönderimi (10ms sonra) |

### 3.2 Ana Simülasyon Döngüsü

```python
while recv_base < total_segments:
    
    # 1. Backpressure kontrolü
    buffer_available = check_combined_buffer()
    
    # 2. Yeni frame gönder (pencere ve buffer müsaitse)
    if can_send() and buffer_available:
        send_new_frame()
    
    # 3. Timeout kontrolü → Selective retransmission
    for seq in get_timed_out_frames():
        retransmit(seq)
    
    # 4. Event işle
    event = pop_next_event()
    handle_event(event)
```

### 3.3 Toplanan Metrikler

| Metrik | Açıklama | Hesaplama |
|--------|----------|-----------|
| `goodput` | Faydalı veri hızı | `(100MB × 8) / total_time` |
| `goodput_mbps` | Mbps cinsinden goodput | `goodput / 10⁶` |
| `total_time` | Toplam simülasyon süresi | Saniye |
| `retransmissions` | Yeniden iletim sayısı | Timeout + Fast retransmit |
| `avg_rtt` | Ortalama RTT | Non-retransmitted paketlerden |
| `utilization` | Kanal kullanım oranı | `total_tx_time / total_time` |
| `buffer_events` | Buffer/integrity hataları | Reddedilen segment sayısı |
| `delayed_acks` | Gecikmeli ACK sayısı | Buffer >80% olayları |

---

## 4. Simülasyon Senaryoları

### 4.1 Parametre Uzayı

```
Window Sizes (W):  [2, 4, 8, 16, 32, 64]  →  6 değer
Payload Sizes (L): [128, 256, 512, 1024, 2048, 4096]  →  6 değer
Seeds:             [0, 1, 2, ..., 9]  →  10 değer
─────────────────────────────────────────────────────
Toplam:            6 × 6 × 10 = 360 simülasyon
```

### 4.2 Beklenen Davranışlar

| Senaryo | Beklenti |
|---------|----------|
| **Küçük W, Küçük L** | Düşük throughput (pipeline yetersiz) |
| **Büyük W, Küçük L** | Header overhead yüksek |
| **Küçük W, Büyük L** | Pipeline yetersiz, büyük frame kaybı maliyetli |
| **Büyük W, Büyük L** | Buffer overflow riski, burst error hassasiyeti |
| **Optimal bölge** | W=64, L=512 civarı (teorik) |

---

## 5. Proje Yapısı

```
commhw2/
│
├── src/                          # Kaynak kodlar
│   ├── __init__.py
│   ├── config.py                 # Tüm sabit parametreler
│   ├── models.py                 # Segment, Frame veri yapıları
│   ├── engine.py                 # Event-driven simülasyon motoru
│   ├── main.py                   # Ana çalıştırma scripti
│   │
│   └── layers/                   # Katman implementasyonları
│       ├── physical.py           # Fiziksel katman + Gilbert-Elliot
│       ├── link.py               # Selective Repeat ARQ
│       └── transport.py          # Segmentasyon + Buffer yönetimi
│
├── analysis/
│   └── plotter.py                # Görselleştirme ve analiz
│
├── simulation_results.csv        # Ham simülasyon sonuçları
├── optimized_results.csv         # İyileştirilmiş sonuçlar
├── goodput_3d.png                # 3D görselleştirme
│
├── HW2.pdf                       # Ödev dökümanı
└── REQUIREMENTS_ANALYSIS.md      # Bu dosya
```

---

## 6. Kullanım

### 6.1 Simülasyonu Çalıştırma

```bash
cd src
python main.py
```

**Çıktı:** `simulation_results.csv`

### 6.2 Hızlı Test (Küçük veri)

```python
from engine import SimulationEngine
import numpy as np

engine = SimulationEngine(W=16, L=512, seed=42)
time = engine.run(np.random.bytes(1024 * 100))  # 100 KB test

print(f"Time: {time:.2f}s")
print(f"Goodput: {(100*1024*8)/time/1e6:.2f} Mbps")
print(f"Avg RTT: {engine.avg_rtt*1000:.1f} ms")
print(f"Utilization: {engine.utilization*100:.1f}%")
print(f"Retransmissions: {engine.retransmissions}")
```

### 6.3 Görselleştirme

```bash
cd analysis
python plotter.py
```

---

## 7. Optimizasyon Özellikleri (Phase 2)

### 7.1 Uygulanan Optimizasyonlar

| Özellik | Açıklama | Etki |
|---------|----------|------|
| **Adaptive Timeout** | Jacobson's Algorithm ile dinamik RTO | Gereksiz retransmit azalır |
| **Fast Retransmit** | 3 dup ACK → anında retransmit | Kayıp tespiti hızlanır |
| **Delayed ACK** | Buffer >80% → 10ms gecikme | Sender yavaşlar, overflow önlenir |

### 7.2 Potansiyel Gelecek İyileştirmeler

- [ ] Piggybacked ACK
- [ ] Silly Window Syndrome prevention  
- [ ] Dynamic window adjustments (congestion control)
- [ ] SACK (Selective Acknowledgment)

---

## 8. Performans Formülleri

### Goodput

```
Goodput = (Total_Payload_Bytes × 8) / Total_Time  [bps]
```

### Channel Utilization

```
Utilization = Total_Transmission_Time / Total_Simulation_Time
```

### Theoretical Maximum Throughput

```
Max_Throughput = BIT_RATE × (1 - Overhead_Ratio)

Overhead_Ratio = (Link_Header + Transport_Header) / (Link_Header + Transport_Header + L)
               = (24 + 8) / (32 + L)
```

| L (bytes) | Overhead | Max Effective Rate |
|-----------|----------|-------------------|
| 128 | 20.0% | 8.0 Mbps |
| 256 | 11.1% | 8.9 Mbps |
| 512 | 5.9% | 9.4 Mbps |
| 1024 | 3.0% | 9.7 Mbps |
| 2048 | 1.5% | 9.85 Mbps |
| 4096 | 0.8% | 9.92 Mbps |

---

## 9. Gereksinim Karşılama Durumu

| Kategori | Durum |
|----------|-------|
| Transport Layer | ✅ Tamamlandı |
| Link Layer (SR ARQ) | ✅ Tamamlandı |
| Physical Layer | ✅ Tamamlandı |
| Gilbert-Elliot Model | ✅ Tamamlandı |
| 360 Simülasyon | ✅ Tamamlandı |
| CSV Çıktısı | ✅ Tüm metrikler dahil |
| Phase 2 Optimizasyonları | ✅ 3/6 (yeterli) |

---

*Son güncelleme: 16 Ocak 2026*
