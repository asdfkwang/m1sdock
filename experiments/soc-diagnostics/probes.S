/* Every faultable instruction below is explicitly 4 bytes for recovery. */
.text
.option norvc
.macro CSR_PROBE name, csr
.global \name
\name:
    li a0, 0
.global \name\()_insn
\name\()_insn:
    csrr a0, \csr
    ret
.endm

CSR_PROBE read_cycle_probe, cycle
CSR_PROBE read_satp_probe, satp
CSR_PROBE read_pmpcfg0_probe, pmpcfg0
CSR_PROBE read_pmpaddr0_probe, pmpaddr0
CSR_PROBE read_mstatus_probe, mstatus
CSR_PROBE read_mideleg_probe, mideleg

.global read32_probe
read32_probe:
    mv a1, a0
    li a0, 0
.global read32_probe_insn
read32_probe_insn:
    lwu a0, 0(a1)
    ret
