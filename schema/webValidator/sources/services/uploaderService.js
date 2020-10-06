import papaparse from "papaparse";
import XLSX from "xlsx";

const ALLOWED_FILE_EXTENSIONS = ["csv", "xls", "xlsx"];

export default class UploaderService {
	constructor(uploader, filesDropDown, uploadMetadataView, view) {
		this.uploader = uploader;
		this.filesDropDown = filesDropDown;
		this.uploadMetadataView = uploadMetadataView;
		this.view = view;

		this.initUploaderEvents();
	}

	initUploaderEvents() {
		this.uploader.addDropZone(this.uploadMetadataView.$view, "Drop files here");
		const fileList = this.filesDropDown.getList();
		this.uploader.attachEvent("onBeforeFileAdd", (file) => { // onBeforeFileDrop
			this.view.showProgress();
			this.parseFile(file)
				.then((data) => {
					fileList.parse([data]);
					this.filesDropDown.setValue(fileList.getLastId());
					this.view.hideProgress();
				})
				.catch((message) => {
					webix.message(message);
					this.view.hideProgress();
				});
		});

		// to prevent the dropping of any item except the file
		this.uploader.attachEvent("onBeforeFileDrop", files => !!files.length);

		fileList.attachEvent("onAfterLoad", () => {
			this.filesDropDown.enable();
		});

		fileList.attachEvent("onAfterDelete", () => {
			if (!fileList.count()) {
				this.filesDropDown.disable();
			}
		});
	}

	parseFile(file) {
		return new Promise((resolve) => {
			let message = `Not allowed filetype: ${file.type}`;

			if (ALLOWED_FILE_EXTENSIONS.includes(file.type)) {
				const fileList = this.filesDropDown.getList();
				if (fileList.find(item => item.name === file.name, true)) {
					message = `File with name "${file.name}" already exists`;
					throw message;
				}

				const fr = new FileReader();
				fr.addEventListener("load", () => {
					const text = file.type === "csv" ? fr.result : this.parseExcel(fr.result);
					const json = papaparse.parse(text, {header: true});
					json.name = file.name;
					resolve(json);
				}, false);

				fr.addEventListener("error", (err) => {
					throw err;
				}, false);

				if (file.type === "csv") {
					fr.readAsText(file.file);
				}
				else {
					fr.readAsBinaryString(file.file);
				}
			}
			else {
				throw message;
			}
		});
	}

	parseExcel(fileResult) {
		const workbook = XLSX.read(fileResult, {
			type: "binary"
		});
		return workbook.SheetNames.reduce((acc, val) => {
			const separator = acc ? "\n" : "";
			acc = `${acc}${separator}${XLSX.utils.sheet_to_csv(workbook.Sheets[val])}`;
			return acc;
		}, "");
	}
}
