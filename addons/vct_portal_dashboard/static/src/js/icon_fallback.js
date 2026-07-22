// Written for VCT Platform. Not part of Odoo S.A.
// Inline onerror= is blocked by Odoo's CSP, so bind the handler from a real
// asset file: a missing app icon collapses to the tile's initial letter.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.vct_lc_tile img').forEach((img) => {
        const drop = () => img.remove();
        if (img.complete && img.naturalWidth === 0) {
            drop();
        } else {
            img.addEventListener('error', drop, { once: true });
        }
    });
});
