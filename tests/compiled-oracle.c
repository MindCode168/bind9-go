/* SPDX-License-Identifier: MPL-2.0 */
/* Thin wrappers around the real, compiled upstream libraries. */
#include <stdint.h>
#include <isc/buffer.h>
#include <isc/region.h>
#include <isc/result.h>
#include <dns/ttl.h>

int bind_go_parse(char *text, unsigned int length, int counter, uint32_t *value) {
    isc_textregion_t input = {text, length};
    isc_result_t result = counter ? dns_counter_fromtext(&input, value)
                                  : dns_ttl_fromtext(&input, value);
    switch (result) {
    case ISC_R_SUCCESS: return 0;
    case ISC_R_RANGE: return 1;
    case DNS_R_SYNTAX: return 2;
    case DNS_R_BADTTL: return 3;
    default: return -1;
    }
}

int bind_go_format(uint32_t value, int verbose, int upcase, char *output) {
    isc_buffer_t buffer;
    isc_buffer_init(&buffer, output, 255);
    isc_result_t result = dns_ttl_totext(value, verbose, upcase, &buffer);
    output[isc_buffer_usedlength(&buffer)] = '\0';
    return result == ISC_R_SUCCESS ? 0 : -1;
}
