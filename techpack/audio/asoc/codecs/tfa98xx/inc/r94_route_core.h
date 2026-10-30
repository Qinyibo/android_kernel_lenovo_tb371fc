/* Portable transaction core; compiled unchanged in kernel and fault harness.
 * Caller holds the device DSP lock. No gain, supply, calibration or OTP access.
 * A failed rollback or mute release retains its ledger for retry/disable.
 */
#ifndef R94_ROUTE_CORE_H
#define R94_ROUTE_CORE_H
struct r94_route_ledger {
 unsigned short original, last, previous;
 unsigned char owned, mute_owned;
};
struct r94_route_ops {
 int (*read)(void *, unsigned char, unsigned short *);
 int (*write_route)(void *, unsigned short);
 int (*mute)(void *, int);
 int (*wait_quiet)(void *);
};
static int r94_release_mute(struct r94_route_ledger *s,
                          const struct r94_route_ops *o, void *p)
{
 unsigned short power, mute;
 if (!s->mute_owned) return 0;
 if (o->mute(p, 0)) return -5;
 if (o->read(p, 0, &power) || o->read(p, 0x51, &mute) ||
     !(power & 8) || (mute & 8)) return -5;
 s->mute_owned = 0;
 return 0;
}
static int r94_route_transaction(struct r94_route_ledger *s,
                                const struct r94_route_ops *o, void *p,
                                unsigned short target, int enable)
{
 unsigned short before_word, power, input, mute, after;
 int ret = 0;
 /* First retry an owned mute release, even if no new route is requested. */
 if (r94_release_mute(s, o, p)) return -5;
 if (!enable && !s->owned) return 0;
 if (o->read(p, 0x23, &before_word)) return -5;
 if (s->owned && before_word != s->last && before_word != s->previous && before_word != s->original) {
  /* Another configuration owns this word. Never restore over it. */
  s->owned = 0;
  return -116;
 }
 if (!enable) target = s->original;
 if (enable && target != 0x0410 && target != 0x0401) return -22;
 if (enable && !s->owned && before_word != 0x0410) return -116;
 if (before_word == target) {
  if (!enable) s->owned = 0;
  return 0;
 }
 if (o->read(p, 0, &power) || o->read(p, 1, &input) ||
     o->read(p, 0x51, &mute)) return -5;
 /* A stopped amplifier needs no mute cycle and must never be powered up
  * merely to relinquish routing. Keep its existing CFSM/power untouched. */
 if (!enable && !(power & 8) && (input & 3) == 2) {
  if (o->read(p, 0x10, &after) || (after & 0x0800)) return -11;
  goto write_word;
 }
 if (!(power & 8) || (power & 1) || (input & 3) != 2 || (mute & 8))
  return -11; /* Refuse preexisting mute; do not claim or clear it. */
 if (!s->owned) { s->original = before_word; s->last = before_word; }
 /* Mark the mute attempt before I/O: an error may still have reached HW. */
 s->mute_owned = 1;
 if (o->mute(p, 1) || o->wait_quiet(p)) { ret = -5; goto out; }
 /* DSP lock held throughout. Refuse any unowned word change during mute. */
 if (o->read(p, 0x23, &after) || after != before_word) {
  ret = -116; goto out;
 }
write_word:
 s->previous = before_word; s->last = target; s->owned = 1;
 if (o->write_route(p, target) || o->read(p, 0x23, &after) || after != target) {
  ret = -5;
  /* Retain ledger until exact original readback confirms rollback. */
  if (!o->read(p, 0x23, &after)) {
   if (after == target || after == before_word) {
    if (!o->write_route(p, s->original) &&
        !o->read(p, 0x23, &after) && after == s->original)
     s->owned = 0;
   } else if (after == s->original) s->owned = 0;
   else s->owned = 0; /* Foreign owner: no overwrite. */
  }
 } else {
  s->previous = target;
  if (!enable) s->owned = 0;
 }
out:
 if (r94_release_mute(s, o, p)) return -5;
 return ret;
}
#endif
