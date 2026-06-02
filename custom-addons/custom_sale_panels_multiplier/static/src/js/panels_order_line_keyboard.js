/** @odoo-module */

import { ProductLabelSectionAndNoteListRender } from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field_o2m";
import { patch } from "@web/core/utils/patch";

const PANELS_ENTER_NAV_COLUMNS = new Set([
    "product_id",
    "product_template_id",
    "thickness",
    "width",
    "length",
    "number_of_panels",
    "product_uom_qty",
    "product_qty",
]);

patch(ProductLabelSectionAndNoteListRender.prototype, {
    _hasPanelsDimensionColumns() {
        return this.columns?.some((c) => c.name === "thickness");
    },

    _shouldPanelsEnterMoveToNextCell(cell, record) {
        if (!this._hasPanelsDimensionColumns() || record?.data?.display_type) {
            return false;
        }
        const columnName = cell?.getAttribute?.("name");
        return columnName && PANELS_ENTER_NAV_COLUMNS.has(columnName);
    },

    onCellKeydownEditMode(hotkey, cell, group, record) {
        if (hotkey === "enter" && this._shouldPanelsEnterMoveToNextCell(cell, record)) {
            if (this.applyCellKeydownEditModeStayOnRow("tab", cell, group, record)) {
                return true;
            }
        }
        return super.onCellKeydownEditMode(hotkey, cell, group, record);
    },
});
