import {errorsCollection} from "../models/errors";

export default class MetaDatatableService {
	constructor({datatable, view}) {
		this.datatable = datatable;
		this.view = view;
		this.setDatatableEventsAndSettings();
	}

	setDatatableEventsAndSettings() {
		this.datatable.getNode().addEventListener("contextmenu", (e) => {
			e.preventDefault();
		});

		this.datatable.attachEvent("onBeforeEditStop", (vals) => {
			vals.value = this.escapeSpecChars(vals.value);
		});

		this.datatable.on_click["adjust-icon"] = (e, obj) => {
			const columnId = obj.column;
			this.datatable.adjustColumn(columnId, "all");
			return false;
		};
	}

	getColumnConfig(fields) {
		const columnConfig = fields.map((field) => {
			if (!field) return null;
			if (field === "filename") {
				return this.getItemNameColumn();
			}
			return {
				id: field,
				header: (() => {
					const name = field.charAt(0).toUpperCase() + field.slice(1);
					return `<div class='upload-metadata-column-header'>
						<span title='${name}' class='column-header-name ellipsis-text'>${name}</span>
						<i title='Adjust column' class="adjust-icon fas fa-arrows-alt-h"></i>
					</div>`;
				})(),
				tooltip: obj => obj[field] || "",
				editor: "text",
				sort: "raw",
				width: 150,
				minWidth: 20
			};
		});

		columnConfig.unshift({
			id: "info",
			width: 40,
			tooltip: (obj) => {
				const errorsList = errorsCollection[obj.id];
				if (errorsList) {
					let text = "<div><b class='strong-font'>Validation failed:</b></div><ul class='validation-error-list'>";
					errorsList.forEach((err) => {
						text += `<li>${err.message}</li>`;
					});
					text += "</ul>";
					return text;
				}
				return "Data is valid";
			},
			template: (obj) => {
				return errorsCollection[obj.id] ? "<i class='warning-icon fas fa-exclamation-circle'></i>" : "<i class='fas fa-thumbs-up'></i>";
			}
		});

		return columnConfig.filter(column => column);
	}

	getItemNameColumn() {
		return {
			id: "filename",
			header: "Filename",
			sort: "raw",
			adjust: true,
			fillspace: true,
			minWidth: 250,
			editor: "text"
		};
	}

	escapeSpecChars(string) {
		return string
			.replace(/>/g, "&gt;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&apos;");
	}

	unescapeSpecChars(string) {
		return string
			.replace(/&gt;/g, ">")
			.replace(/&lt;/g, "<")
			.replace(/&quot;/g, "\"")
			.replace(/&apos;/g, "'");
	}
}
