# Architecture

## Hexagonal layout

The domain core depends on nothing. Adapters depend on the ports they
implement. The composition root in `app/` is the only place that knows
about concrete adapter classes.

```mermaid
flowchart LR
    subgraph Domain["domain/ (pure)"]
        SM[StateMachine]
        VD[VarianceDetector]
        EV[events]
    end

    subgraph Ports["ports/"]
        PClock[Clock]
        PCsi[CsiSource]
        PNotif[Notifier]
        PSiren[Siren]
        PStore[Store]
    end

    subgraph Adapters["adapters/"]
        direction TB
        ACsi["csi/<br/>synthetic · nexmon"]
        ANotif["notifier/<br/>console · telegram · email · composite"]
        ASiren["siren/<br/>mock · gpio"]
        AClock["clock/<br/>system · fake"]
        AStore["store/<br/>memory · sqlite"]
    end

    subgraph App["app/"]
        Comp[composition.compose]
        Run[runtime.run]
        Cfg[config.AlarmConfig]
    end

    SM --> EV
    VD --> EV

    ACsi -.implements.-> PCsi
    ANotif -.implements.-> PNotif
    ASiren -.implements.-> PSiren
    AClock -.implements.-> PClock
    AStore -.implements.-> PStore

    Cfg --> Comp
    Comp --> Adapters
    Comp --> Domain
    Run --> Comp
```

## Runtime: three concurrent loops

```mermaid
flowchart TD
    CSI[CsiSource]
    DET[VarianceDetector]
    SM[StateMachine]
    NOTIF[Notifier]
    SIREN[Siren]
    STORE[Store]
    CLK[Clock]

    CSI -- CsiFrame --> CAP{{capture_loop}}
    CAP --> DET
    DET -- MotionEvent --> SM

    NOTIF -- UserReply / UserCommand --> INB{{inbound_loop}}
    INB --> SM

    CLK --> TICK{{tick_loop · 1Hz}}
    TICK --> SM

    SM -- NotifyOwner --> NOTIF
    SM -- SirenOn / SirenOff --> SIREN
    SM -- LogEvent --> STORE
```

## State machine

```mermaid
stateDiagram-v2
    [*] --> DISARMED
    DISARMED --> ARMED: /arm
    ARMED --> ALERTING: motion
    ALERTING --> ARMED: dismiss
    ALERTING --> TRIGGERED: confirm
    ALERTING --> TRIGGERED: timeout (REPLY_TIMEOUT_S)
    TRIGGERED --> DISARMED: /disarm
    ARMED --> TRIGGERED: /panic
    ALERTING --> TRIGGERED: /panic
    DISARMED --> TRIGGERED: /panic
    ARMED --> DISARMED: /snooze N
    note right of DISARMED
        After /snooze N, auto-rearm to ARMED
        when N minutes elapse
    end note
```
