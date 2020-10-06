import DatatableService from "./datatableService";
import UploaderService from "./uploaderService";

class MetadataUploadService {
	constructor(view) {
		this._view = view;
		this._ready();
	}

	_ready() {
		webix.extend(this._view, webix.ProgressBar);
		// child views
		const scope = this._view.$scope;
		this._uploader = scope.uploader;
		this._uploadMetadataView = scope.uploadMetadataView;
		this._sidebarTree = scope.sidebarTree;
		this._filesDropDown = scope.filesDropDown;
		this._filesList = this._filesDropDown.getList();
		this._metaDatatable = scope.metaDatatable;
		this._loadSchemaButton = scope.loadSchemaButton;
		this._schemaStatusTemplate = scope.schemaStatusTemplate;

		this._datatableService = new DatatableService({
			datatable: this._metaDatatable,
			view: this._view
		});
		this._uploaderService = new UploaderService(
			this._uploader,
			this._filesDropDown,
			this._uploadMetadataView,
			this._view
		);

		this._filesDropDown.attachEvent("onChange", (id) => {
			const list = this._filesDropDown.getList();
			this._metaDatatable.clearAll();
			if (id) {
				const metaItem = list.getItem(id);

				const columnConfig = this._datatableService.getColumnConfig(metaItem.meta.fields);
				this._metaDatatable.refreshColumns(columnConfig);
				this._metaDatatable.parse(metaItem.data);
				this._metaDatatable.validate();
			}
			else {
				this._metaDatatable.refreshColumns([]);
			}
		});

		this._filesList.attachEvent("onItemClick", (id, ev) => {
			if (ev.target.classList.contains("delete-icon")) {
				this._filesList.remove(id);
				return false;
			}
		});

		this._loadSchemaButton.attachEvent("onItemClick", () => {
			const form = this._loadSchemaButton.getFormView();
			if (form.validate()) {
				const url = form.getValues().url;
				this._schemaStatusTemplate.setValues({progress: true});
				webix.ajax().get(url)
					.then((data) => {
						this._schemaStatusTemplate.setValues({progress: false});
						webix.storage.local.put("currentSchema", data.text());
					})
					.catch((err) => {
						this._schemaStatusTemplate.setValues({progress: false});
						webix.message(err.message || "Unexpected error");
					});
			}
		});
	}
}

export default MetadataUploadService;
